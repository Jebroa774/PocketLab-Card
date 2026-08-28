"""Explicitly tent every routed PCB via on both board sides.

KiCad's board-level tenting option is a default for newly-created vias.  Older
vias can retain an explicit/legacy "not tented" state, which leaves tiny mask
webs around dense routing.  This utility normalizes routed vias without moving
copper or changing connectivity.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    changed = 0

    for item in board.GetTracks():
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        before = (item.GetFrontTentingMode(), item.GetBackTentingMode())
        item.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        item.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        after = (item.GetFrontTentingMode(), item.GetBackTentingMode())
        changed += before != after

    pcbnew.SaveBoard(str(args.output.resolve()), board)
    print(f"explicitly tented {changed} routed vias")


if __name__ == "__main__":
    main()
