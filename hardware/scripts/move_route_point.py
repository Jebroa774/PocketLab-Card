"""Move one explicit point in selected KiCad segment/via UUIDs."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from restore_baseline_net import POINT_RE, coord_key, copper_blocks, format_coordinate


def point(value: str) -> tuple[float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("points must use x,y")
    return float(parts[0]), float(parts[1])


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--uuid", action="append", required=True)
    parser.add_argument("--old", type=point, required=True)
    parser.add_argument("--new", type=point, required=True)
    parser.add_argument("--refill", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    input_path = args.input.resolve()
    text = input_path.read_text(encoding="utf-8")
    requested = set(args.uuid)
    selected = [block for block in copper_blocks(text) if block[3] in requested]
    found = {block[3] for block in selected}
    if found != requested:
        raise RuntimeError(f"Missing UUID(s): {', '.join(sorted(requested - found))}")
    old_key = coord_key(args.old)
    replacements: list[tuple[int, int, str]] = []
    changed = 0
    for start, end, _kind, _uuid, _net in selected:
        block = text[start:end]

        def replace(match):
            nonlocal changed
            value = float(match.group(2)), float(match.group(3))
            if coord_key(value) != old_key:
                return match.group(0)
            changed += 1
            return (
                f"({match.group(1)} {format_coordinate(args.new[0])} "
                f"{format_coordinate(args.new[1])}"
            )

        replacements.append((start, end, POINT_RE.sub(replace, block)))
    if changed == 0:
        raise RuntimeError("Selected copper does not contain --old")
    for start, end, block in sorted(replacements, reverse=True):
        text = text[:start] + block + text[end:]
    output_path.write_text(text, encoding="utf-8", newline="\n")
    if args.refill:
        board = pcbnew.LoadBoard(str(output_path))
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(f"Moved {changed} selected route point(s) from {args.old} to {args.new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
