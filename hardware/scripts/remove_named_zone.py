"""Remove one named helper zone from a PCB working candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    authoritative = (Path(__file__).resolve().parent.parent / "PocketLab-Card.kicad_pcb").resolve()
    if output == authoritative:
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    matches = [zone for zone in board.Zones() if zone.GetZoneName() == args.name]
    if not matches:
        raise RuntimeError(f"Zone not found: {args.name}")
    for zone in matches:
        board.Remove(zone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output), board)
    print(f"REMOVED_ZONES {len(matches)} name={args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
