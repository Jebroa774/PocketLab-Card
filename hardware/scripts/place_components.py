"""Create the first physical placement draft with real KiCad footprints.

This is deliberately a placement-only generator. It does not invent a netlist
or pretend that the empty schematic sheets are electrically complete. Run it
with KiCad's bundled Python, validate the staging board, then replace the main
board only after closing PCB Editor.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pcbnew


@dataclass(frozen=True)
class Placement:
    reference: str
    value: str
    library: str
    footprint: str
    x_mm: float
    y_mm: float
    rotation_deg: float = 0.0
    position_is_footprint_origin: bool = False


PLACEMENTS = (
    # For U1 the library origin is the module body center. Its courtyard also
    # includes Espressif's much larger antenna clearance and must not be used
    # as the centering box.
    Placement("U1", "ESP32-S3-WROOM-1-N8R2", "RF_Module", "ESP32-S3-WROOM-1", 87.0, 32.75, 0.0, True),
    Placement("U2", "PN5321A3HN/C106", "Package_DFN_QFN", "HVQFN-40-1EP_6x6mm_P0.5mm_EP4.1x4.1mm", 53.8, 41.0),
    Placement("U3", "E07-900M10S", "PocketLab_Custom", "E07-900M10S", 88.0, 62.0, 90.0),
    Placement("U4", "MAX-M10S-00B", "RF_GPS", "ublox_MAX", 66.6, 33.7),
    Placement("U5", "BQ24074RGTR", "Package_DFN_QFN", "VQFN-16-1EP_3x3mm_P0.5mm_EP1.6x1.6mm", 78.0, 51.5),
    Placement("U7", "TPS61023DRLR", "Package_TO_SOT_SMD", "SOT-563", 69.5, 60.5),
    Placement("U8", "MAX17048G+T10", "Package_DFN_QFN", "TDFN-8-1EP_2x2mm_P0.5mm_EP0.8x1.2mm", 78.0, 61.0),
    Placement("U9", "TCA9535PWR", "Package_SO", "TSSOP-24_4.4x7.8mm_P0.65mm", 46.5, 31.5, 90.0),
    Placement("U10", "BMI270 (FULL option)", "Package_LGA", "Bosch_LGA-14_3x2.5mm_P0.5mm", 49.0, 47.5),
    Placement("U12", "PCF8563T", "Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", 42.0, 44.5),
    Placement("Q1", "AO3400A IR driver", "Package_TO_SOT_SMD", "SOT-23", 97.5, 56.0, 90.0),
    Placement("LED1", "WS2812B-2020", "LED_SMD", "LED_WS2812B-2020_PLCC4_2.0x2.0mm", 31.0, 32.0),
    Placement("LED2", "WS2812B-2020", "LED_SMD", "LED_WS2812B-2020_PLCC4_2.0x2.0mm", 37.0, 32.0),
    Placement("LED3", "WS2812B-2020", "LED_SMD", "LED_WS2812B-2020_PLCC4_2.0x2.0mm", 31.0, 39.0),
    Placement("LED4", "WS2812B-2020", "LED_SMD", "LED_WS2812B-2020_PLCC4_2.0x2.0mm", 37.0, 39.0),
    Placement("D1", "TSAL6200 940nm IR (bend toward edge)", "LED_THT", "LED_D5.0mm", 103.0, 56.0),
    Placement("J1", "USB-C data/power", "Connector_USB", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", 101.9, 46.5, 270.0),
    Placement("J2", "microSD", "Connector_Card", "microSD_HC_Molex_104031-0811", 30.75, 66.5),
    Placement("J3", "GNSS ANT", "Connector_Coaxial", "U.FL_Hirose_U.FL-R-SMT-1_Vertical", 64.0, 24.0),
    Placement("J4", "BAT 1S 3.7V", "Connector_JST", "JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal", 101.8, 64.0, 270.0),
    Placement("J5", "2x15 2.54mm EXPANSION", "Connector_PinHeader_2.54mm", "PinHeader_2x15_P2.54mm_Vertical", 59.0, 69.45, 90.0),
)


def vec_mm(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(x_mm, y_mm)


def footprint_root() -> Path:
    # KiCad's bundled python.exe lives at <kicad>/bin/python.exe.
    return Path(sys.executable).resolve().parent.parent / "share" / "kicad" / "footprints"


def load_footprint(hardware_dir: Path, spec: Placement) -> pcbnew.FOOTPRINT:
    if spec.library == "PocketLab_Custom":
        library_dir = hardware_dir / "PocketLab_Custom.pretty"
    else:
        library_dir = footprint_root() / f"{spec.library}.pretty"

    footprint = pcbnew.FootprintLoad(str(library_dir), spec.footprint)
    if footprint is None:
        raise RuntimeError(f"Footprint not found: {spec.library}:{spec.footprint}")

    footprint.SetFPID(pcbnew.LIB_ID(spec.library, spec.footprint))
    footprint.SetReference(spec.reference)
    footprint.SetValue(spec.value)
    footprint.Value().SetVisible(False)
    return footprint


def place_footprint(footprint: pcbnew.FOOTPRINT, spec: Placement) -> None:
    footprint.SetOrientationDegrees(spec.rotation_deg)
    footprint.SetPosition(vec_mm(0.0, 0.0))
    footprint.BuildCourtyardCaches()
    courtyard = footprint.GetCourtyard(pcbnew.F_CrtYd).BBox()
    if courtyard.GetWidth() <= 0 or courtyard.GetHeight() <= 0:
        raise RuntimeError(f"{footprint.GetReference()} has no usable F.CrtYd")

    target = vec_mm(spec.x_mm, spec.y_mm)
    if spec.position_is_footprint_origin:
        footprint.SetPosition(target)
    else:
        center = courtyard.GetCenter()
        footprint.Move(pcbnew.VECTOR2I(target.x - center.x, target.y - center.y))

    placed_box = footprint.GetCourtyard(pcbnew.F_CrtYd).BBox()
    reference = footprint.Reference()
    reference.SetVisible(True)
    reference.SetLayer(pcbnew.F_SilkS)
    reference.SetTextSize(vec_mm(0.8, 0.8))
    reference.SetTextThickness(pcbnew.FromMM(0.12))
    reference.SetPosition(
        pcbnew.VECTOR2I(placed_box.GetCenter().x, placed_box.GetTop() - pcbnew.FromMM(0.7))
    )


def add_rect(board: pcbnew.BOARD, x1: float, y1: float, x2: float, y2: float, layer: int) -> None:
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(pcbnew.SHAPE_T_RECT)
    shape.SetStart(vec_mm(x1, y1))
    shape.SetEnd(vec_mm(x2, y2))
    shape.SetLayer(layer)
    shape.SetWidth(pcbnew.FromMM(0.2))
    board.Add(shape)


def add_text(board: pcbnew.BOARD, text: str, x_mm: float, y_mm: float, layer: int, size_mm: float = 1.0) -> None:
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetPosition(vec_mm(x_mm, y_mm))
    item.SetLayer(layer)
    item.SetTextSize(vec_mm(size_mm, size_mm))
    item.SetTextThickness(pcbnew.FromMM(max(0.12, size_mm * 0.15)))
    item.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    board.Add(item)


def add_placement_guides(board: pcbnew.BOARD) -> None:
    # NFC copper is deliberately not drawn yet: these rectangles are only the
    # outer and inner planning boundaries for later antenna calculation/tuning.
    add_rect(board, 22.8, 23.5, 59.0, 52.5, pcbnew.Dwgs_User)
    add_rect(board, 25.8, 26.5, 56.0, 49.5, pcbnew.Dwgs_User)
    add_text(board, "NFC LOOP RESERVE - NOT ROUTED", 40.9, 51.0, pcbnew.Cmts_User, 0.9)

    add_rect(board, 61.5, 45.5, 81.0, 65.0, pcbnew.Dwgs_User)
    add_text(board, "POWER ISLAND", 71.25, 64.0, pcbnew.Cmts_User, 0.9)

    # Exact custom land patterns are still being created from manufacturer
    # package drawings; these are honest placement envelopes, not fake pads.
    add_rect(board, 65.0, 49.0, 72.0, 55.0, pcbnew.Dwgs_User)
    add_text(board, "U6 TPS63070 + L", 68.5, 52.0, pcbnew.Cmts_User, 0.75)
    add_rect(board, 51.0, 45.8, 55.0, 49.8, pcbnew.Dwgs_User)
    add_text(board, "U11 BMP390", 53.0, 48.0, pcbnew.Cmts_User, 0.65)
    add_rect(board, 72.0, 39.5, 77.0, 44.5, pcbnew.Dwgs_User)
    add_text(board, "U13 IR RX", 74.5, 42.0, pcbnew.Cmts_User, 0.65)

    add_text(board, "PLACEMENT DRAFT - UNROUTED / NOT FOR PRODUCTION", 62.8, 72.8, pcbnew.Cmts_User, 0.95)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.input.resolve()
    output = args.output.resolve()
    # Resolve project-local libraries from the script location so the input
    # scaffold may live in hardware/templates without changing library lookup.
    hardware_dir = Path(__file__).resolve().parent.parent
    board = pcbnew.LoadBoard(str(source))

    title_block = board.GetTitleBlock()
    title_block.SetRevision("PLACEMENT-DRAFT")
    title_block.SetComment(1, "4-layer, 1.6 mm; schematic/netlist and routing incomplete")

    existing = list(board.GetFootprints())
    if existing:
        refs = ", ".join(sorted(fp.GetReference() for fp in existing))
        raise RuntimeError(f"Input board is not an empty placement scaffold; existing refs: {refs}")

    # Remove the old scaffold caption while preserving the exact Edge.Cuts.
    for drawing in list(board.GetDrawings()):
        if isinstance(drawing, pcbnew.PCB_TEXT) and "MECHANICAL SCAFFOLD" in drawing.GetText():
            board.Remove(drawing)

    for spec in PLACEMENTS:
        footprint = load_footprint(hardware_dir, spec)
        place_footprint(footprint, spec)
        board.Add(footprint)

    add_placement_guides(board)
    pcbnew.SaveBoard(str(output), board)

    reloaded = pcbnew.LoadBoard(str(output))
    refs = sorted(fp.GetReference() for fp in reloaded.GetFootprints())
    if len(refs) != len(PLACEMENTS):
        raise RuntimeError(f"Round-trip lost footprints: expected {len(PLACEMENTS)}, got {len(refs)}")

    print(f"Saved {len(refs)} real footprints to {output}")
    print("References: " + ", ".join(refs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
