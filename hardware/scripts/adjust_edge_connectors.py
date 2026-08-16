"""Apply reviewed inward edge-connector placement adjustments to a candidate PCB."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


J2_POSITION_MM = (99.1, 39.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    main_board = Path(__file__).resolve().parent.parent / "PocketLab-Card.kicad_pcb"
    if output_path == main_board.resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    connector = board.FindFootprintByReference("J2")
    if connector is None:
        raise RuntimeError("J2 is missing")
    connector.SetPosition(pcbnew.VECTOR2I_MM(*J2_POSITION_MM))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    print(f"Saved edge-connector candidate: {output_path}; J2={J2_POSITION_MM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
