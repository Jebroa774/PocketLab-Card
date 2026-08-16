"""Complete the wide common-cathode path from D1 to the existing D2/D3 bus."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


POINTS = (
    (32.25, 54.51),
    (30.6, 55.5),
    (30.6, 61.95),
    (30.75, 62.1),
)


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
    for start, end in zip(POINTS, POINTS[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I_MM(*start))
        track.SetEnd(pcbnew.VECTOR2I_MM(*end))
        track.SetWidth(pcbnew.FromMM(0.5))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(board.FindNet("/IR_LED_K"))
        track.SetLocked(True)
        board.Add(track)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    print(f"Saved IR cathode candidate: {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
