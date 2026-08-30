"""Add the two short, wide outer-layer NFC antenna feed traces.

The script only writes a candidate board.  A full KiCad DRC comparison is the
acceptance gate before the candidate may replace the main PCB.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


FEEDS = (
    (
        "/NFC_LOOP_A",
        (
            (47.9125, 22.2),
            (47.9125, 20.8),
            (45.12, 20.8),
            (45.12, 23.1),
            (44.71, 23.1),
            (44.71, 24.25),
        ),
    ),
    (
        "/NFC_LOOP_B",
        ((40.4125, 22.2), (41.0, 23.0), (42.17, 23.0), (42.17, 24.25)),
    ),
)


def add_segment(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: int,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(*start))
    track.SetEnd(pcbnew.VECTOR2I_MM(*end))
    track.SetWidth(pcbnew.FromMM(0.4))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


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
    for net_name, front_points in FEEDS:
        for start, end in zip(front_points, front_points[1:]):
            add_segment(board, net_name, start, end, pcbnew.F_Cu)
        print(
            f"CANDIDATE {net_name}: via-free F.Cu {front_points}",
            flush=True,
        )
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    print(f"Saved NFC antenna-feed candidate: {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
