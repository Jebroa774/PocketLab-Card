"""Restore compact, reviewed SMD-to-plane links removed during cleanup."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


LINKS = {
    "U22.5": {
        "end": (76.85, 42.05),
        "layer": pcbnew.F_Cu,
        "width": 0.15,
        "via": (0.45, 0.20),
    },
    "U9.24": {
        "end": (60.0875, 27.425),
        "layer": pcbnew.B_Cu,
        "width": 0.15,
        "via": (0.45, 0.20),
    },
}


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--link", action="append", choices=sorted(LINKS), required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}
    for label in args.link:
        reference, number = label.split(".", 1)
        pad = next(
            pad for pad in footprints[reference].Pads() if pad.GetNumber() == number
        )
        link = LINKS[label]
        end = link["end"]
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pad.GetPosition())
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(link["width"]))
        track.SetLayer(link["layer"])
        track.SetNet(pad.GetNet())
        track.SetLocked(True)
        board.Add(track)

        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(*end))
        via.SetWidth(pcbnew.FromMM(link["via"][0]))
        via.SetDrill(pcbnew.FromMM(link["via"][1]))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(pad.GetNet())
        via.SetLocked(True)
        board.Add(via)
        print(f"Restored {label} -> plane via at {end[0]:.4f}, {end[1]:.4f}")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
