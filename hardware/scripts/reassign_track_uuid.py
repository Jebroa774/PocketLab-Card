"""Move one routed track segment to another copper layer in a candidate board."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


LAYER_BY_NAME = {
    "F.Cu": pcbnew.F_Cu,
    "In1.Cu": pcbnew.In1_Cu,
    "In2.Cu": pcbnew.In2_Cu,
    "B.Cu": pcbnew.B_Cu,
}


def uuid_text(item: pcbnew.BOARD_ITEM) -> str:
    value = item.m_Uuid
    return value.AsString() if hasattr(value, "AsString") else str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--track-uuid", required=True)
    parser.add_argument("--layer", choices=tuple(LAYER_BY_NAME), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    hardware_dir = Path(__file__).resolve().parent.parent
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    working = (hardware_dir / "PocketLab-Card-routing-working.kicad_pcb").resolve()
    if args.output.resolve() in {authoritative, working, args.input.resolve()}:
        raise RuntimeError("output must be a separate non-authoritative board")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    matches = [item for item in board.GetTracks() if uuid_text(item) == args.track_uuid]
    if len(matches) != 1 or isinstance(matches[0], pcbnew.PCB_VIA):
        raise RuntimeError("UUID must select exactly one track segment")
    track = matches[0]
    old_layer = track.GetLayer()
    track.SetLayer(LAYER_BY_NAME[args.layer])

    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    opens = int(connectivity.GetUnconnectedCount(False))
    if opens:
        raise RuntimeError(f"layer reassignment created {opens} open connection(s)")

    pcbnew.SaveBoard(str(args.output.resolve()), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix)
        )
    print(
        f"REASSIGNED uuid={args.track_uuid} net={track.GetNetname()} "
        f"length={pcbnew.ToMM(track.GetLength()):.4f} "
        f"{board.GetLayerName(old_layer)}->{args.layer} opens={opens}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
