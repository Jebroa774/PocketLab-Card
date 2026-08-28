"""Print copper and pads connected geometrically at a selected via."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def uuid_text(item: pcbnew.BOARD_ITEM) -> str:
    value = item.m_Uuid
    return value.AsString() if hasattr(value, "AsString") else str(value)


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--uuid", required=True)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    matches = [item for item in board.GetTracks() if uuid_text(item) == args.uuid]
    if len(matches) != 1 or not isinstance(matches[0], pcbnew.PCB_VIA):
        raise RuntimeError("UUID must select exactly one via")
    via = matches[0]
    position = via.GetPosition()
    print(
        f"VIA {args.uuid} net={via.GetNetname()} pos={xy(position)} "
        f"diameter={pcbnew.ToMM(via.GetWidth(pcbnew.F_Cu)):.3f} "
        f"drill={pcbnew.ToMM(via.GetDrillValue()):.3f}"
    )
    for item in board.GetTracks():
        if isinstance(item, pcbnew.PCB_VIA):
            continue
        if item.GetStart() == position or item.GetEnd() == position:
            print(
                f"  TRACK {uuid_text(item)} net={item.GetNetname()} "
                f"layer={board.GetLayerName(item.GetLayer())} "
                f"start={xy(item.GetStart())} end={xy(item.GetEnd())} "
                f"width={pcbnew.ToMM(item.GetWidth()):.3f}"
            )
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetPosition() == position:
                print(
                    f"  PAD {footprint.GetReference()}.{pad.GetNumber()} "
                    f"net={pad.GetNetname()} layers={list(pad.GetLayerSet().Seq())} "
                    f"size={xy(pad.GetSize())} orientation={pad.GetOrientationDegrees():.1f} "
                    f"footprint_pos={xy(footprint.GetPosition())}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
