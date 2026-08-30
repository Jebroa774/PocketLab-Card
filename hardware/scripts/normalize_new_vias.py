"""Tent and normalize only vias added after a reviewed base board."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from prune_new_drc_conflicts import geometry_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diameter", type=float, default=0.40)
    parser.add_argument("--drill", type=float, default=0.18)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    hardware_dir = Path(__file__).resolve().parent.parent
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if args.output.resolve() in {
        authoritative,
        args.base.resolve(),
        args.candidate.resolve(),
    }:
        raise RuntimeError("output must be a separate non-authoritative board")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")
    if args.diameter - args.drill < 0.20 - 1e-9:
        raise RuntimeError("via geometry must preserve at least a 0.10 mm annular ring")

    base = pcbnew.LoadBoard(str(args.base.resolve()))
    candidate = pcbnew.LoadBoard(str(args.candidate.resolve()))
    base_keys = {geometry_key(item) for item in base.GetTracks()}
    normalized = 0
    for item in candidate.GetTracks():
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        if geometry_key(item) in base_keys:
            continue
        item.SetWidth(pcbnew.FromMM(args.diameter))
        item.SetDrill(pcbnew.FromMM(args.drill))
        item.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        item.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
        normalized += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output.resolve()), candidate)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix)
        )
    print(f"NORMALIZED vias={normalized} diameter={args.diameter} drill={args.drill}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
