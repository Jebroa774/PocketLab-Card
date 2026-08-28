"""Replace a connected set of tracks with one explicitly defined polyline."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


def uuid_text(item: pcbnew.BOARD_ITEM) -> str:
    value = item.m_Uuid
    return value.AsString() if hasattr(value, "AsString") else str(value)


def parse_point(value: str) -> tuple[float, float]:
    pieces = value.split(",")
    if len(pieces) != 2:
        raise argparse.ArgumentTypeError("point must be X,Y in millimetres")
    return float(pieces[0]), float(pieces[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--remove-uuid", action="append", required=True)
    parser.add_argument("--point", action="append", type=parse_point, required=True)
    parser.add_argument("--layer", choices=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"), required=True)
    parser.add_argument("--width", type=float, default=0.15)
    parser.add_argument("--fill-zones", action="store_true")
    parser.add_argument("--require-zero-open", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.resolve() == args.input.resolve():
        raise RuntimeError("output must differ from input")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")
    if len(args.point) < 2:
        raise RuntimeError("at least two points are required")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    wanted = set(args.remove_uuid)
    matches = [item for item in board.GetTracks() if uuid_text(item) in wanted]
    found = {uuid_text(item) for item in matches}
    if found != wanted or any(isinstance(item, pcbnew.PCB_VIA) for item in matches):
        raise RuntimeError(f"track UUID mismatch: wanted={sorted(wanted)} found={sorted(found)}")
    nets = {item.GetNetCode() for item in matches}
    if len(nets) != 1:
        raise RuntimeError(f"removed tracks must share one net, got {sorted(nets)}")
    net = matches[0].GetNet()
    locked = any(item.IsLocked() for item in matches)
    for item in matches:
        board.Remove(item)

    layer = board.GetLayerID(args.layer)
    added = 0
    for start, end in zip(args.point, args.point[1:]):
        if abs(start[0] - end[0]) < 0.001 and abs(start[1] - end[1]) < 0.001:
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pcbnew.VECTOR2I_MM(*start))
        track.SetEnd(pcbnew.VECTOR2I_MM(*end))
        track.SetLayer(layer)
        track.SetWidth(pcbnew.FromMM(args.width))
        track.SetNet(net)
        track.SetLocked(locked)
        board.Add(track)
        added += 1

    if args.fill_zones:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    opens = int(connectivity.GetUnconnectedCount(False))
    if args.require_zero_open and opens:
        raise RuntimeError(f"replacement created {opens} open connection(s)")

    pcbnew.SaveBoard(str(args.output.resolve()), board)
    hardware_dir = Path(__file__).resolve().parent.parent
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix))
    print(
        f"REROUTED net={net.GetNetname()} layer={args.layer} "
        f"removed={len(matches)} segments={added} opens={opens}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
