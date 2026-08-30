"""Rehome two reviewed plane fanouts away from the J5/notch routing neck."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from route_plane_fanouts import item_key


REMOVE = {
    "/GND": frozenset(
        {
            "5bbc51b6-dfa7-4945-a7c0-12f4dec9ece6",
            "3794bbaf-9328-46d4-8e1b-f9bb9b4e7346",
        }
    ),
    "/+5V_RAW": frozenset(
        {
            "c798d998-0cc8-4677-a6f7-a605b8157187",
            "fada25dc-91e8-4497-8d36-693647dfabef",
        }
    ),
}

TRACKS = (
    ("/GND", pcbnew.F_Cu, (68.0500, 63.8625), (69.0500, 63.8625), 0.20),
    ("/+5V_RAW", pcbnew.B_Cu, (66.4500, 65.9000), (65.4500, 64.9000), 0.20),
    ("/+5V_RAW", pcbnew.B_Cu, (65.4500, 64.9000), (65.4500, 64.7750), 0.20),
    ("/+5V_RAW", pcbnew.B_Cu, (65.4500, 64.7750), (64.8250, 64.7750), 0.20),
    ("/+5V_RAW", pcbnew.B_Cu, (64.8250, 64.7750), (64.271557, 64.665323), 0.20),
)

VIAS = (
    ("/GND", 69.0500, 63.8625),
)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(*position)


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    matches = [candidate for candidate in footprint.Pads() if candidate.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}.{number} pad, got {len(matches)}")
    return matches[0]


def via_at(board: pcbnew.BOARD, net_name: str, position: tuple[float, float]) -> pcbnew.PCB_VIA:
    matches = [
        item
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA)
        and item.GetNetname() == net_name
        and item.GetPosition() == point(position)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {net_name} via at {position}, got {len(matches)}")
    return matches[0]


def track_exists(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    wanted_start = point(start)
    wanted_end = point(end)
    return any(
        not isinstance(item, pcbnew.PCB_VIA)
        and item.GetNetname() == net_name
        and item.GetLayer() == layer
        and (
            (item.GetStart() == wanted_start and item.GetEnd() == wanted_end)
            or (item.GetStart() == wanted_end and item.GetEnd() == wanted_start)
        )
        for item in board.GetTracks()
    )


def connected(board: pcbnew.BOARD, first: pcbnew.BOARD_ITEM, second: pcbnew.BOARD_ITEM) -> bool:
    board.BuildConnectivity()
    wanted = item_key(second)
    return any(
        item_key(candidate) == wanted
        for candidate in board.GetConnectivity().GetConnectedItems(first)
    )


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(start))
    track.SetEnd(point(end))
    track.SetWidth(pcbnew.FromMM(width))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def add_via(board: pcbnew.BOARD, net_name: str, position: tuple[float, float]) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(position))
    via.SetWidth(pcbnew.FromMM(0.45))
    via.SetDrill(pcbnew.FromMM(0.20))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(board.FindNet(net_name))
    via.SetLocked(True)
    board.Add(via)


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    try:
        via_at(board, "/GND", (69.05, 63.8625))
        already_rehomed = all(
            track_exists(board, net_name, layer, start, end)
            for net_name, layer, start, end, _width in TRACKS
        )
    except RuntimeError:
        already_rehomed = False
    if not already_rehomed:
        wanted = set().union(*REMOVE.values())
        selected = {item_key(item): item for item in board.GetTracks() if item_key(item) in wanted}
        missing = wanted.difference(selected)
        if missing:
            raise RuntimeError(f"Reviewed fanout copper is missing: {', '.join(sorted(missing))}")
        for net_name, uuids in REMOVE.items():
            changed = [uuid for uuid in uuids if selected[uuid].GetNetname() != net_name]
            if changed:
                raise RuntimeError(f"Reviewed {net_name} copper changed net: {', '.join(changed)}")
        for item in selected.values():
            board.RemoveNative(item)
        for net_name, layer, start, end, width in TRACKS:
            add_track(board, net_name, layer, start, end, width)
        for net_name, x_value, y_value in VIAS:
            add_via(board, net_name, (x_value, y_value))

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    reloaded = pcbnew.LoadBoard(str(output_path))
    checks = (
        ("Q1.2 GND", pad(reloaded, "Q1", "2"), via_at(reloaded, "/GND", (69.05, 63.8625))),
        (
            "C609.1 +5V_RAW",
            pad(reloaded, "C609", "1"),
            via_at(reloaded, "/+5V_RAW", (64.271557, 64.665323)),
        ),
    )
    failed = [label for label, first, second in checks if not connected(reloaded, first, second)]
    if failed:
        raise RuntimeError(f"Rehomed fanout connectivity failed: {', '.join(failed)}")
    connectivity = reloaded.GetConnectivity()
    connectivity.RecalculateRatsnest()
    print(
        f"Saved rehomed fanout candidate: {output_path}; "
        f"unconnected={int(connectivity.GetUnconnectedCount(False))}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
