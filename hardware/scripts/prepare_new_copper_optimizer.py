"""Lock base copper and expose only candidate-added copper to FreeRouting."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


def geometry_key(item: pcbnew.BOARD_ITEM) -> tuple:
    if isinstance(item, pcbnew.PCB_VIA):
        return (
            "via",
            item.GetPosition().x,
            item.GetPosition().y,
            item.GetWidth(pcbnew.F_Cu),
            item.GetDrillValue(),
            int(item.GetViaType()),
            item.TopLayer(),
            item.BottomLayer(),
            item.GetNetname(),
        )
    first = (item.GetStart().x, item.GetStart().y)
    second = (item.GetEnd().x, item.GetEnd().y)
    if second < first:
        first, second = second, first
    return (
        "track",
        first,
        second,
        item.GetWidth(),
        item.GetLayer(),
        item.GetNetname(),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dsn", type=Path, required=True)
    parser.add_argument("--net", action="append")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.resolve() in {args.base.resolve(), args.candidate.resolve()}:
        raise RuntimeError("output must differ from base and candidate")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")

    base = pcbnew.LoadBoard(str(args.base.resolve()))
    candidate = pcbnew.LoadBoard(str(args.candidate.resolve()))
    base_keys = {geometry_key(item) for item in base.GetTracks()}
    selected_nets = set(args.net or ())
    locked = 0
    routable = 0
    for item in candidate.GetTracks():
        if geometry_key(item) in base_keys:
            item.SetLocked(True)
            locked += 1
        elif not selected_nets or item.GetNetname() in selected_nets:
            item.SetLocked(False)
            routable += 1
        else:
            item.SetLocked(True)
            locked += 1

    pcbnew.SaveBoard(str(args.output.resolve()), candidate)
    if not pcbnew.ExportSpecctraDSN(candidate, str(args.dsn.resolve())):
        raise RuntimeError("Specctra DSN export failed")
    hardware_dir = Path(__file__).resolve().parent.parent
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix))
    print(f"OPTIMIZER_INPUT locked_base={locked} routable_new={routable}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
