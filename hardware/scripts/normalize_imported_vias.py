"""Normalize too-small annular rings after a Specctra SES import."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-ring", type=float, default=0.10)
    parser.add_argument(
        "--mode",
        choices=("shrink-drill", "enlarge-diameter"),
        default="shrink-drill",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = args.input.resolve()
    output = args.output.resolve()
    if not source.is_file():
        raise RuntimeError(f"Input PCB does not exist: {source}")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")
    if source == output:
        raise RuntimeError("Input and output must differ")

    board = pcbnew.LoadBoard(str(source))
    changed = 0
    for item in board.GetTracks():
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        drill_mm = pcbnew.ToMM(item.GetDrillValue())
        diameter_mm = pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu))
        maximum_drill_mm = diameter_mm - 2.0 * args.minimum_ring
        if drill_mm <= maximum_drill_mm + 1e-9:
            continue
        if args.mode == "shrink-drill":
            item.SetDrill(pcbnew.FromMM(maximum_drill_mm))
        else:
            item.SetWidth(pcbnew.FromMM(drill_mm + 2.0 * args.minimum_ring))
        changed += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output), board)
    hardware_dir = Path(__file__).resolve().parent.parent
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix)
        )
    print(f"NORMALIZED_VIAS {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
