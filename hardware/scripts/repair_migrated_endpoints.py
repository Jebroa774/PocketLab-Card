"""Reconnect reviewed short track ends after passive-footprint migration.

The factory-footprint migration keeps component centres fixed.  Smaller 0603
and compact IC footprints move their lands slightly towards the centre, while
the accepted legacy tracks still end at the former pad centres.  This pass
adds only short, collinear/local bridges between those two positions.  Large
component moves and switch/connector replacements are deliberately excluded.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil

import pcbnew


REVIEWED_REFS = frozenset(
    {
        "C123",
        "C201",
        "C505",
        "C516",
        "L6",
        "R116",
        "R120",
        "R129",
        "R201",
        "R402",
        "R509",
        "R512",
        "R513",
        "R517",
        "R607",
        "R609",
        "R732",
        "R736",
        "U22",
    }
)

MAX_SHIFT_MM = 0.80
POSITION_TOLERANCE_MM = 0.002


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return position.x / 1_000_000.0, position.y / 1_000_000.0


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(
        pcbnew.FromMM(position[0]), pcbnew.FromMM(position[1])
    )


def close(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return math.dist(first, second) <= POSITION_TOLERANCE_MM


def track_touches(track: pcbnew.PCB_TRACK, position: tuple[float, float]) -> bool:
    return close(xy(track.GetStart()), position) or close(xy(track.GetEnd()), position)


def track_exists(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    first: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    for track in board.GetTracks():
        if not isinstance(track, pcbnew.PCB_TRACK) or isinstance(track, pcbnew.PCB_VIA):
            continue
        if track.GetNetname() != net_name or track.GetLayer() != layer:
            continue
        start, end = xy(track.GetStart()), xy(track.GetEnd())
        if (close(start, first) and close(end, second)) or (
            close(start, second) and close(end, first)
        ):
            return True
    return False


def pad_map(board: pcbnew.BOARD) -> dict[str, dict[str, pcbnew.PAD]]:
    return {
        footprint.GetReference(): {pad.GetNumber(): pad for pad in footprint.Pads()}
        for footprint in board.GetFootprints()
    }


def repair(
    baseline: pcbnew.BOARD,
    board: pcbnew.BOARD,
    reviewed_refs: frozenset[str] = REVIEWED_REFS,
    reviewed_pads: frozenset[str] | None = None,
    direct_retarget: bool = False,
) -> list[str]:
    baseline_pads = pad_map(baseline)
    current_pads = pad_map(board)
    added: list[str] = []

    for reference in sorted(reviewed_refs):
        if reference not in baseline_pads or reference not in current_pads:
            continue
        for number, old_pad in baseline_pads[reference].items():
            if reviewed_pads is not None and f"{reference}.{number}" not in reviewed_pads:
                continue
            new_pad = current_pads[reference].get(number)
            if new_pad is None or new_pad.GetNetname() != old_pad.GetNetname():
                continue
            old_position = xy(old_pad.GetPosition())
            new_position = xy(new_pad.GetPosition())
            shift = math.dist(old_position, new_position)
            if shift <= POSITION_TOLERANCE_MM or shift > MAX_SHIFT_MM:
                continue

            old_tracks = [
                track
                for track in baseline.GetTracks()
                if isinstance(track, pcbnew.PCB_TRACK)
                and not isinstance(track, pcbnew.PCB_VIA)
                and track.GetNetname() == old_pad.GetNetname()
                and track_touches(track, old_position)
            ]
            for layer in sorted({track.GetLayer() for track in old_tracks}):
                if not new_pad.IsOnLayer(layer):
                    continue
                # Cleanup may have removed the complete former end segment as
                # dangling copper.  Restore that already-reviewed segment
                # first, then bridge its old pad-centre endpoint to the new
                # compact land.
                direct_added = False
                for source in [track for track in old_tracks if track.GetLayer() == layer]:
                    source_start, source_end = xy(source.GetStart()), xy(source.GetEnd())
                    retained_exact = track_exists(
                        board,
                        new_pad.GetNetname(),
                        layer,
                        source_start,
                        source_end,
                    )
                    if retained_exact:
                        continue
                    replacement_start, replacement_end = source_start, source_end
                    if direct_retarget:
                        if close(source_start, old_position):
                            replacement_start = new_position
                        elif close(source_end, old_position):
                            replacement_end = new_position
                        if track_exists(
                            board,
                            new_pad.GetNetname(),
                            layer,
                            replacement_start,
                            replacement_end,
                        ):
                            direct_added = True
                            continue
                    restored = pcbnew.PCB_TRACK(board)
                    restored.SetStart(point(replacement_start))
                    restored.SetEnd(point(replacement_end))
                    restored.SetWidth(source.GetWidth())
                    restored.SetLayer(layer)
                    restored.SetNet(new_pad.GetNet())
                    restored.SetLocked(True)
                    board.Add(restored)
                    added.append(
                        f"{reference}.{number} {new_pad.GetNetname()} "
                        f"{pcbnew.LayerName(layer)} "
                        f"{'retargeted' if direct_retarget else 'restored legacy end'}"
                    )
                    direct_added = direct_added or direct_retarget

                if direct_added:
                    continue

                retained = [
                    track
                    for track in board.GetTracks()
                    if isinstance(track, pcbnew.PCB_TRACK)
                    and not isinstance(track, pcbnew.PCB_VIA)
                    and track.GetNetname() == new_pad.GetNetname()
                    and track.GetLayer() == layer
                    and track_touches(track, old_position)
                ]
                if not retained or track_exists(
                    board,
                    new_pad.GetNetname(),
                    layer,
                    new_position,
                    old_position,
                ):
                    continue

                source_widths = [
                    track.GetWidth()
                    for track in old_tracks
                    if track.GetLayer() == layer
                ]
                bridge = pcbnew.PCB_TRACK(board)
                bridge.SetStart(point(new_position))
                bridge.SetEnd(point(old_position))
                bridge.SetWidth(min(source_widths))
                bridge.SetLayer(layer)
                bridge.SetNet(new_pad.GetNet())
                bridge.SetLocked(True)
                board.Add(bridge)
                added.append(
                    f"{reference}.{number} {new_pad.GetNetname()} "
                    f"{pcbnew.LayerName(layer)} {shift:.3f} mm"
                )
    return added


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--refs",
        help="Optional comma-separated subset of reviewed reference designators",
    )
    parser.add_argument(
        "--pads",
        help="Optional comma-separated subset of reviewed REF.PAD labels",
    )
    parser.add_argument(
        "--direct-retarget",
        action="store_true",
        help="Move the old segment endpoint directly to the compact pad",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    baseline_path = args.baseline.resolve()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    protected_main = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if output_path == protected_main:
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    baseline = pcbnew.LoadBoard(str(baseline_path))
    board = pcbnew.LoadBoard(str(input_path))
    reviewed_refs = REVIEWED_REFS
    if args.refs:
        requested = frozenset(item.strip() for item in args.refs.split(",") if item.strip())
        unknown = requested - REVIEWED_REFS
        if unknown:
            raise RuntimeError(f"Unreviewed reference(s): {', '.join(sorted(unknown))}")
        reviewed_refs = requested
    reviewed_pads = None
    if args.pads:
        reviewed_pads = frozenset(item.strip() for item in args.pads.split(",") if item.strip())
        pad_refs = frozenset(label.rsplit(".", 1)[0] for label in reviewed_pads)
        unknown = pad_refs - REVIEWED_REFS
        if unknown:
            raise RuntimeError(f"Unreviewed pad reference(s): {', '.join(sorted(unknown))}")
        reviewed_refs = pad_refs
    added = repair(
        baseline,
        board,
        reviewed_refs,
        reviewed_pads,
        direct_retarget=args.direct_retarget,
    )
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(f"Added {len(added)} migrated-pad endpoint bridges")
    for description in added:
        print(f"  {description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
