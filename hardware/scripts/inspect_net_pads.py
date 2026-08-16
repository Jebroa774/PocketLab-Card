"""Print absolute footprint-pad positions for one PCB net.

The helper intentionally avoids iterating board tracks; KiCad 10 SWIG track
iteration can be very slow on this large routed board.  It is a read-only
diagnostic used when an unrouted DRC group is represented by a track endpoint.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--net", required=True)
    args = parser.parse_args()
    net_name = args.net if args.net.startswith("/") else f"/{args.net}"
    board = pcbnew.LoadBoard(str(args.input.resolve()))
    rows: list[tuple[float, float, str, str, str]] = []
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetname() != net_name:
                continue
            position = pad.GetPosition()
            rows.append(
                (
                    pcbnew.ToMM(position.x),
                    pcbnew.ToMM(position.y),
                    footprint.GetReference(),
                    pad.GetNumber(),
                    board.GetLayerName(pad.GetLayer()),
                )
            )
    for x, y, reference, number, layer in sorted(rows):
        print(f"{reference}.{number}\t{x:.6f},{y:.6f}\t{layer}")
    print(f"pads={len(rows)} net={net_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
