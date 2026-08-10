"""Add and fill the two intentional PocketLab Card inner power planes.

The placement builder deliberately creates no arbitrary copper.  This separate
staging step gives FreeRouting real conduction areas while keeping the tracked
main board protected.  L2 is a continuous GND plane.  L3 carries +3V3 except
below the two back-side switching-regulator/inductor loops, where explicit
plane-only rule areas prevent switch-noise coupling into the logic rail.  All
other rails remain short, reviewed outer-layer routes/pours.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    import pcbnew
except ImportError as error:  # pragma: no cover - exercised by the CLI guard
    raise SystemExit("Run with KiCad 10's bundled Python (pcbnew is required)") from error


PLANE_SPECS = (
    ("L2_GND_PLANE", pcbnew.In1_Cu, "/GND"),
    ("L3_3V3_PLANE", pcbnew.In2_Cu, "/+3V3"),
)

# In2.Cu is the layer directly above the back-side switching regulators.  A
# +3V3 plane below their IC/inductor loops would be an unwanted capacitive
# return for switch-node energy.  Keep the continuous In1.Cu GND plane, but
# remove +3V3 below the complete converter/inductor envelopes and bridge
# between them.  The bounds are derived from the final placement so a later
# deliberate move cannot leave a stale coordinate-only cutout behind.
SWITCH_PLANE_KEEPOUTS = (
    ("L3_U6_L6_SWITCH_KEEPOUT", ("U6", "L6")),
    ("L3_U7_L7_SWITCH_KEEPOUT", ("U7", "L7")),
)
SWITCH_PLANE_KEEPOUT_MARGIN_MM = 0.50


def snapshot(board: pcbnew.BOARD) -> tuple[int, int, frozenset[str]]:
    return (
        len(list(board.GetFootprints())),
        len(list(board.GetTracks())),
        frozenset(
            pad.GetNetname()
            for footprint in board.GetFootprints()
            for pad in footprint.Pads()
            if pad.GetNetname()
        ),
    )


def validate_stack(board: pcbnew.BOARD) -> None:
    if board.GetCopperLayerCount() != 4:
        raise RuntimeError(f"Expected four copper layers, got {board.GetCopperLayerCount()}")
    for layer, expected_type in (
        (pcbnew.F_Cu, pcbnew.LT_SIGNAL),
        (pcbnew.In1_Cu, pcbnew.LT_POWER),
        (pcbnew.In2_Cu, pcbnew.LT_POWER),
        (pcbnew.B_Cu, pcbnew.LT_SIGNAL),
    ):
        if not board.IsLayerEnabled(layer) or board.GetLayerType(layer) != expected_type:
            raise RuntimeError(
                f"Unexpected layer setup for {board.GetLayerName(layer)}; "
                "expected signal/power/power/signal"
            )


def make_plane(
    board: pcbnew.BOARD,
    outline: pcbnew.SHAPE_POLY_SET,
    name: str,
    layer: int,
    net_name: str,
) -> pcbnew.ZONE:
    net = board.FindNet(net_name)
    if net is None or net.GetNetCode() <= 0:
        raise RuntimeError(f"Required plane net is absent: {net_name}")
    zone = pcbnew.ZONE(board)
    zone.SetZoneName(name)
    zone.SetLayer(layer)
    zone.SetNet(net)
    zone.SetOutline(outline)
    zone.SetLocalClearance(pcbnew.FromMM(0.25))
    zone.SetMinThickness(pcbnew.FromMM(0.20))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.25))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.30))
    zone.SetMinIslandArea(0)
    zone.SetAssignedPriority(0)
    return zone


def footprint_envelope(
    board: pcbnew.BOARD, references: tuple[str, ...], margin_mm: float
) -> tuple[int, int, int, int]:
    boxes = []
    for reference in references:
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"Switch-plane keepout footprint is absent: {reference}")
        boxes.append(footprint.GetBoundingBox(False, False))
    margin = pcbnew.FromMM(margin_mm)
    return (
        min(box.GetLeft() for box in boxes) - margin,
        min(box.GetTop() for box in boxes) - margin,
        max(box.GetRight() for box in boxes) + margin,
        max(box.GetBottom() for box in boxes) + margin,
    )


def make_plane_keepout(
    board: pcbnew.BOARD, name: str, references: tuple[str, ...]
) -> pcbnew.ZONE:
    zone = pcbnew.ZONE(board)
    zone.SetZoneName(name)
    zone.SetLayer(pcbnew.In2_Cu)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowTracks(False)
    zone.SetDoNotAllowVias(False)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    # Mutate the zone-owned polygon directly.  Passing a temporary
    # SHAPE_POLY_SET through SetOutline loses the rule-area outline in KiCad
    # 10's SWIG bindings after save/reload.
    left, top, right, bottom = footprint_envelope(
        board, references, SWITCH_PLANE_KEEPOUT_MARGIN_MM
    )
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
        outline.Append(pcbnew.VECTOR2I(x, y))
    return zone


def validate_output(path: Path, original: tuple[int, int, frozenset[str]]) -> None:
    board = pcbnew.LoadBoard(str(path))
    if snapshot(board) != original:
        raise RuntimeError("Plane save/reload changed footprints, tracks or pad nets")
    zones = {zone.GetZoneName(): zone for zone in board.Zones()}
    expected_zone_names = {spec[0] for spec in PLANE_SPECS} | {
        spec[0] for spec in SWITCH_PLANE_KEEPOUTS
    }
    if set(zones) != expected_zone_names:
        raise RuntimeError(f"Unexpected zone set after reload: {sorted(zones)}")
    for name, references in SWITCH_PLANE_KEEPOUTS:
        keepout = zones[name]
        if (
            keepout.GetLayer() != pcbnew.In2_Cu
            or not keepout.GetIsRuleArea()
            or not keepout.GetDoNotAllowZoneFills()
        ):
            raise RuntimeError(f"Switch-plane keepout identity changed: {name}")
        left, top, right, bottom = footprint_envelope(
            board, references, SWITCH_PLANE_KEEPOUT_MARGIN_MM
        )
        outline_box = keepout.Outline().BBox()
        actual = (
            outline_box.GetLeft(),
            outline_box.GetTop(),
            outline_box.GetRight(),
            outline_box.GetBottom(),
        )
        if actual != (left, top, right, bottom):
            raise RuntimeError(f"Switch-plane keepout bounds changed: {name}")
    for name, layer, net_name in PLANE_SPECS:
        zone = zones[name]
        if zone.GetLayer() != layer or zone.GetNetname() != net_name:
            raise RuntimeError(f"Plane identity changed after reload: {name}")
        if not zone.IsFilled() or not zone.HasFilledPolysForLayer(layer):
            raise RuntimeError(f"Plane did not retain a filled polygon: {name}")
        filled = zone.GetFilledPolysList(layer)
        if filled.OutlineCount() < 1 or filled.VertexCount() < 4:
            raise RuntimeError(f"Plane fill is empty: {name}")
        # These points are well inside the two footprint-embedded all-layer
        # keepouts, not near their relief edges.  A future footprint/placement
        # change must not silently restore plane copper below either antenna.
        for label, x_mm, y_mm in (
            ("NFC loop interior", 40.9, 38.0),
            ("ESP32 antenna", 93.0, 22.0),
        ):
            if filled.Contains(pcbnew.VECTOR2I_MM(x_mm, y_mm)):
                raise RuntimeError(f"{name} leaked copper into the {label} keepout")
        if layer == pcbnew.In2_Cu:
            for keepout_name, references in SWITCH_PLANE_KEEPOUTS:
                left, top, right, bottom = footprint_envelope(
                    board, references, SWITCH_PLANE_KEEPOUT_MARGIN_MM
                )
                probe = pcbnew.VECTOR2I((left + right) // 2, (top + bottom) // 2)
                if filled.Contains(probe):
                    raise RuntimeError(
                        f"{name} leaked copper into {keepout_name}"
                    )


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Add filled L2 GND and L3 +3V3 planes to a separate staging PCB.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=hardware_dir / "PocketLab-Card-netlisted.kicad_pcb",
        help="validated placement board",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=hardware_dir / "PocketLab-Card-planed.kicad_pcb",
        help="separate plane-filled staging board",
    )
    parser.add_argument("--force", action="store_true", help="replace an existing staging output")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    protected_main = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if input_path == output_path:
        raise RuntimeError("Input and output must differ; the placement board is preserved")
    if output_path == protected_main:
        raise RuntimeError("Refusing to overwrite hardware/PocketLab-Card.kicad_pcb")
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output already exists; pass --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    validate_stack(board)
    if list(board.Zones()):
        raise RuntimeError("Input already contains zones; refusing to duplicate or reinterpret them")
    original = snapshot(board)

    outline = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outline, False):
        raise RuntimeError("Board outline is not a valid closed polygon")
    if outline.OutlineCount() != 1 or outline.VertexCount() < 8:
        raise RuntimeError(
            f"Expected one rounded card outline, got {outline.OutlineCount()} outline(s) "
            f"and {outline.VertexCount()} vertices"
        )

    for spec in SWITCH_PLANE_KEEPOUTS:
        board.Add(make_plane_keepout(board, *spec))
    for spec in PLANE_SPECS:
        board.Add(make_plane(board, outline, *spec))
    if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
        raise RuntimeError("KiCad zone filler failed")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    validate_output(output_path, original)
    print(f"Saved plane-filled staging board: {output_path}")
    print(
        "L2: continuous GND; L3: +3V3 with U6/L6 and U7/L7 switch-area cutouts; "
        "embedded NFC and ESP keepouts preserved by KiCad fill"
    )
    print("Outer-layer power routes, RF ground stitching and final zone review remain manual")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
