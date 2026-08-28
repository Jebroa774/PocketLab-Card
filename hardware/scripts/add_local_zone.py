"""Add one rectangular local copper zone to a PCB candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def parse_xy(value: str) -> tuple[float, float]:
    try:
        x, y = value.split(",", 1)
        return float(x), float(y)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected X,Y in millimetres") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument(
        "--layer", choices=("F.Cu", "GND", "PWR", "B.Cu"), required=True
    )
    parser.add_argument("--corner", type=parse_xy, action="append", required=True)
    parser.add_argument("--clearance", type=float, default=0.20)
    parser.add_argument("--min-thickness", type=float, default=0.15)
    parser.add_argument("--priority", type=int, default=10)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if len(args.corner) != 2:
        raise RuntimeError("provide exactly two opposite --corner values")
    if args.input.resolve() == args.output.resolve():
        raise RuntimeError("output must differ from input")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists; use --force: {args.output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    if any(zone.GetZoneName() == args.name for zone in board.Zones()):
        raise RuntimeError(f"zone already exists: {args.name}")
    net = board.FindNet(args.net)
    if net is None or net.GetNetCode() <= 0:
        raise RuntimeError(f"net does not exist: {args.net}")

    layers = {
        "F.Cu": pcbnew.F_Cu,
        "GND": pcbnew.In1_Cu,
        "PWR": pcbnew.In2_Cu,
        "B.Cu": pcbnew.B_Cu,
    }
    x1, y1 = args.corner[0]
    x2, y2 = args.corner[1]
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))

    zone = pcbnew.ZONE(board)
    zone.SetZoneName(args.name)
    zone.SetLayer(layers[args.layer])
    zone.SetNet(net)
    zone.SetLocalClearance(pcbnew.FromMM(args.clearance))
    zone.SetMinThickness(pcbnew.FromMM(args.min_thickness))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetMinIslandArea(0)
    zone.SetAssignedPriority(args.priority)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
        outline.Append(pcbnew.VECTOR2I_MM(x, y))
    board.Add(zone)

    if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
        raise RuntimeError("zone refill failed")
    pcbnew.SaveBoard(str(args.output.resolve()), board)
    print(
        f"Saved {args.output}: {args.name} {args.net} {args.layer} "
        f"({left},{top})-({right},{bottom})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
