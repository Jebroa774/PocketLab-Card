"""Restore one reviewed baseline net after factory-footprint migration.

Only copper belonging to the explicitly requested net is copied. Segment
ends that formerly landed on a slightly smaller migrated pad are moved to the
new pad centre; large component moves are intentionally not inferred.

KiCad's SWIG ``BOARD.GetTracks()`` iterator can block on large v10 boards, so
the copper blocks are handled as native KiCad S-expressions. pcbnew is used
only for the stable footprint/pad API.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import shutil

import pcbnew


MAX_PAD_SHIFT_MM = 0.80
COPPER_START_RE = re.compile(r"(?m)^\t\((?P<kind>segment|via)\b")
UUID_RE = re.compile(r'\(uuid "([^"]+)"\)')
NET_RE = re.compile(r'\(net "([^"]+)"\)')
POINT_RE = re.compile(r"\((start|end|at)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return position.x / 1_000_000.0, position.y / 1_000_000.0


def coord_key(position: tuple[float, float]) -> tuple[int, int]:
    return round(position[0] * 1_000_000), round(position[1] * 1_000_000)


def footprints(board: pcbnew.BOARD) -> dict[str, pcbnew.FOOTPRINT]:
    return {footprint.GetReference(): footprint for footprint in board.GetFootprints()}


def pad_retargets(
    baseline: pcbnew.BOARD,
    board: pcbnew.BOARD,
    net_name: str,
) -> dict[tuple[int, int], tuple[float, float]]:
    old_footprints = footprints(baseline)
    new_footprints = footprints(board)
    result: dict[tuple[int, int], tuple[float, float]] = {}
    for reference, old_footprint in old_footprints.items():
        new_footprint = new_footprints.get(reference)
        if new_footprint is None:
            continue
        new_pads = {pad.GetNumber(): pad for pad in new_footprint.Pads()}
        for old_pad in old_footprint.Pads():
            if old_pad.GetNetname() != net_name:
                continue
            new_pad = new_pads.get(old_pad.GetNumber())
            if new_pad is None or new_pad.GetNetname() != net_name:
                continue
            old_position, new_position = xy(old_pad.GetPosition()), xy(new_pad.GetPosition())
            shift = math.dist(old_position, new_position)
            if 0.002 < shift <= MAX_PAD_SHIFT_MM:
                result[coord_key(old_position)] = new_position
    return result


def copper_blocks(text: str) -> list[tuple[int, int, str, str, str]]:
    """Return ``(start, end, kind, uuid, net)`` for top-level copper blocks."""
    result: list[tuple[int, int, str, str, str]] = []
    for match in COPPER_START_RE.finditer(text):
        start = match.start()
        depth = 0
        end = None
        for index in range(start, len(text)):
            character = text[index]
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    if end < len(text) and text[end] == "\r":
                        end += 1
                    if end < len(text) and text[end] == "\n":
                        end += 1
                    break
        if end is None:
            raise RuntimeError(f"Unterminated {match.group('kind')} block at byte {start}")
        block = text[start:end]
        uuid_match = UUID_RE.search(block)
        net_match = NET_RE.search(block)
        if uuid_match and net_match:
            result.append(
                (start, end, match.group("kind"), uuid_match.group(1), net_match.group(1))
            )
    return result


def format_coordinate(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def retarget_block(
    block: str,
    retargets: dict[tuple[int, int], tuple[float, float]],
) -> str:
    def replace(match: re.Match[str]) -> str:
        old = (float(match.group(2)), float(match.group(3)))
        new = retargets.get(coord_key(old))
        if new is None:
            return match.group(0)
        return (
            f"({match.group(1)} {format_coordinate(new[0])} "
            f"{format_coordinate(new[1])}"
        )

    return POINT_RE.sub(replace, block)


def restore(
    baseline_text: str,
    board_text: str,
    net_name: str,
    retargets: dict[tuple[int, int], tuple[float, float]],
    selected_uuids: set[str] | None = None,
) -> tuple[str, int, int]:
    source_blocks: dict[str, tuple[str, str]] = {}
    for start, end, kind, uuid, net in copper_blocks(baseline_text):
        if net == net_name and (selected_uuids is None or uuid in selected_uuids):
            source_blocks[uuid] = (kind, retarget_block(baseline_text[start:end], retargets))
    if not source_blocks:
        raise RuntimeError(f"Baseline has no copper for net: {net_name}")

    replacements: list[tuple[int, int, str]] = []
    present: set[str] = set()
    for start, end, _kind, uuid, net in copper_blocks(board_text):
        if net != net_name or uuid not in source_blocks:
            continue
        replacements.append((start, end, source_blocks[uuid][1]))
        present.add(uuid)

    for start, end, block in sorted(replacements, reverse=True):
        board_text = board_text[:start] + block + board_text[end:]

    additions = [block for uuid, (_kind, block) in source_blocks.items() if uuid not in present]
    if additions:
        insertion = board_text.find("\n\t(zone\n")
        if insertion < 0:
            insertion = board_text.rfind("\n)")
        board_text = board_text[:insertion] + "\n" + "".join(additions) + board_text[insertion:]

    segments = sum(1 for kind, _block in source_blocks.values() if kind == "segment")
    vias = sum(1 for kind, _block in source_blocks.values() if kind == "via")
    return board_text, segments, vias


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument(
        "--uuid",
        action="append",
        default=[],
        help="Restore only the selected baseline copper UUID; may be repeated",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")
    net_name = args.net if args.net.startswith("/") else f"/{args.net}"
    baseline_path = args.baseline.resolve()
    input_path = args.input.resolve()
    baseline = pcbnew.LoadBoard(str(baseline_path))
    board = pcbnew.LoadBoard(str(input_path))
    retargets = pad_retargets(baseline, board, net_name)
    restored_text, segments, vias = restore(
        baseline_path.read_text(encoding="utf-8"),
        input_path.read_text(encoding="utf-8"),
        net_name,
        retargets,
        set(args.uuid) if args.uuid else None,
    )
    output_path.write_text(restored_text, encoding="utf-8", newline="\n")
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(
        f"Restored {net_name}: segments={segments}; vias={vias}; "
        f"retargets={len(retargets)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
