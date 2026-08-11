"""Add the first reviewed, local critical routes to the routing staging PCB.

This is deliberately a small deterministic pass, not a general autorouter.
Only compact reviewed connections whose endpoints are fixed by the placement
builder belong here.  KiCad DRC remains the acceptance test after every pass.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


SEGMENTS: tuple[
    tuple[str, float, int, tuple[float, float], tuple[float, float]], ...
] = (
    # Buck-boost switch nodes: a 0.20-mm package neck widens immediately to
    # 0.60 mm and remains entirely on B.Cu.
    ("/U6_L1", 0.20, pcbnew.B_Cu, (66.25, 43.50), (65.60, 43.2963)),
    ("/U6_L1", 0.60, pcbnew.B_Cu, (65.60, 43.2963), (62.50, 42.325)),
    ("/U6_L2", 0.20, pcbnew.B_Cu, (66.25, 44.50), (65.60, 44.7037)),
    ("/U6_L2", 0.60, pcbnew.B_Cu, (65.60, 44.7037), (62.50, 45.675)),
    ("/U7_SW", 0.20, pcbnew.B_Cu, (80.7875, 44.00), (80.00, 44.00)),
    ("/U7_SW", 0.60, pcbnew.B_Cu, (80.00, 44.00), (78.65, 44.00)),
    # U7 feedback divider and feed-forward capacitor: join the regulator FB
    # pin directly to the already-routed divider spine without a via.
    ("/U7_FB", 0.20, pcbnew.B_Cu, (82.2125, 43.50), (84.50, 43.50)),
    # U7 5-V output loop.  C115 is the local output capacitor; the branch to
    # R120/C113 stays below C120 and clear of R109 before reaching the divider.
    ("/+5V_RAW", 0.20, pcbnew.B_Cu, (80.7875, 43.50), (80.7875, 42.70)),
    ("/+5V_RAW", 0.50, pcbnew.B_Cu, (80.7875, 42.70), (80.35, 41.65)),
    # This is a Kelvin/sense branch to the feedback divider, not the load
    # current path.  Its 0.20-mm width fits between C120 and C115.
    ("/+5V_RAW", 0.20, pcbnew.B_Cu, (80.35, 41.65), (79.65, 41.65)),
    ("/+5V_RAW", 0.20, pcbnew.B_Cu, (79.65, 41.65), (79.65, 40.475)),
    ("/+5V_RAW", 0.20, pcbnew.B_Cu, (79.65, 40.475), (84.50, 40.475)),
    ("/+5V_RAW", 0.20, pcbnew.B_Cu, (84.50, 40.475), (84.50, 40.8875)),
    ("/+5V_RAW", 0.50, pcbnew.B_Cu, (84.50, 40.8875), (86.40, 41.025)),
    # U7 input-current loop.  The VSYS path passes below the switch-node route
    # and ties both the VIN pin and its local input capacitor to L7 pad 1.
    ("/VSYS", 0.50, pcbnew.B_Cu, (75.35, 44.00), (75.35, 46.25)),
    ("/VSYS", 0.50, pcbnew.B_Cu, (75.35, 46.25), (81.60, 46.25)),
    ("/VSYS", 0.20, pcbnew.B_Cu, (82.2125, 44.50), (82.2125, 45.30)),
    ("/VSYS", 0.50, pcbnew.B_Cu, (82.2125, 45.30), (81.60, 46.25)),
    ("/VSYS", 0.50, pcbnew.B_Cu, (81.60, 46.25), (82.05, 47.50)),
    # U6 input and output capacitors are connected directly to the converter
    # power lands.  These short paths stay outside the two switch-node loops.
    ("/VSYS", 0.50, pcbnew.B_Cu, (66.50, 42.60), (65.825, 40.80)),
    ("/VSYS", 0.50, pcbnew.B_Cu, (65.825, 40.80), (62.95, 39.80)),
    ("/+3V3", 0.50, pcbnew.B_Cu, (66.50, 45.40), (66.50, 46.845)),
    ("/+3V3", 0.50, pcbnew.B_Cu, (66.50, 46.845), (67.95, 46.845)),
    # Native ESP32-S3 USB pair.  R201/R202 are vertical and side-by-side so
    # the stacked MCU pins fan into a left/right pair without a crossing or
    # layer transition.  The pair remains on F.Cu through U16.
    ("/USB_D_N", 0.20, pcbnew.F_Cu, (83.85, 42.73), (82.55, 42.73)),
    ("/USB_D_N", 0.20, pcbnew.F_Cu, (82.55, 42.73), (82.55, 45.80)),
    ("/USB_D_N", 0.20, pcbnew.F_Cu, (82.55, 45.80), (83.25, 46.40)),
    ("/USB_D_N", 0.20, pcbnew.F_Cu, (83.25, 46.40), (83.65, 46.80)),
    ("/USB_D_P", 0.20, pcbnew.F_Cu, (83.85, 44.00), (83.20, 44.70)),
    ("/USB_D_P", 0.20, pcbnew.F_Cu, (83.20, 44.70), (83.20, 45.80)),
    ("/USB_D_P", 0.20, pcbnew.F_Cu, (83.20, 45.80), (83.90, 46.40)),
    ("/USB_D_P", 0.20, pcbnew.F_Cu, (83.90, 46.40), (86.56, 46.40)),
    ("/USB_D_P", 0.20, pcbnew.F_Cu, (86.56, 46.40), (86.56, 47.2375)),
    ("/USB_CONN_N", 0.20, pcbnew.F_Cu, (84.30, 49.0625), (85.00, 48.25)),
    ("/USB_CONN_N", 0.20, pcbnew.F_Cu, (85.00, 48.25), (92.80, 48.25)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (86.56, 49.0625), (85.40, 48.70)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (85.40, 48.70), (91.80, 48.70)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (91.80, 48.70), (91.80, 50.00)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (91.80, 50.00), (95.55, 50.00)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (95.55, 50.00), (94.45, 49.45)),
    # USB-C A/B pad bridge.  Two 0.50/0.30-mm via columns sit 0.60 mm apart;
    # the local 0.15-mm copper clearance matches J1's native fine-pitch land
    # pattern while the holes retain the normal drill clearances.
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (95.55, 50.00), (97.00, 50.95)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (97.00, 50.95), (98.555, 50.95)),
    ("/USB_CONN_P", 0.20, pcbnew.B_Cu, (97.00, 50.95), (97.00, 51.95)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (97.00, 51.95), (98.555, 51.95)),
    ("/USB_CONN_N", 0.20, pcbnew.F_Cu, (92.50, 48.8625), (92.50, 48.25)),
    ("/USB_CONN_N", 0.20, pcbnew.B_Cu, (92.50, 48.25), (93.00, 48.50)),
    ("/USB_CONN_N", 0.20, pcbnew.B_Cu, (93.00, 48.50), (95.80, 48.50)),
    ("/USB_CONN_N", 0.20, pcbnew.B_Cu, (95.80, 48.50), (96.40, 48.60)),
    ("/USB_CONN_N", 0.20, pcbnew.B_Cu, (96.40, 48.60), (96.40, 51.45)),
    ("/USB_CONN_N", 0.20, pcbnew.F_Cu, (96.40, 51.45), (98.555, 51.45)),
    ("/USB_CONN_N", 0.20, pcbnew.B_Cu, (96.40, 51.45), (96.40, 52.45)),
    ("/USB_CONN_N", 0.20, pcbnew.F_Cu, (96.40, 52.45), (98.555, 52.45)),
    # USB-C CC2 pull-down and ESD branch.  R102/J1 B5 stay on F.Cu.  U16 pin 6
    # changes to B.Cu inside its pad, passes through the centre gap of C103 and
    # returns to the dual-sided J1 B5 land below the two data-bridge columns.
    # The two 0.50/0.30-mm vias are ordinary through vias; L2/L3 remain free of
    # signal tracks and therefore retain their continuous reference planes.
    ("/USB_CC2", 0.20, pcbnew.F_Cu, (96.24, 46.7875), (97.30, 46.7875)),
    ("/USB_CC2", 0.20, pcbnew.F_Cu, (97.30, 46.7875), (97.35, 48.80)),
    ("/USB_CC2", 0.20, pcbnew.F_Cu, (97.35, 48.80), (97.35, 49.95)),
    ("/USB_CC2", 0.20, pcbnew.F_Cu, (97.35, 49.95), (98.555, 49.95)),
    ("/USB_CC2", 0.20, pcbnew.B_Cu, (94.40, 50.90), (94.15, 51.10)),
    ("/USB_CC2", 0.20, pcbnew.B_Cu, (94.15, 51.10), (94.15, 53.075)),
    ("/USB_CC2", 0.20, pcbnew.B_Cu, (94.15, 53.075), (97.70, 53.075)),
    ("/USB_CC2", 0.20, pcbnew.B_Cu, (97.70, 53.075), (97.70, 49.95)),
    ("/USB_CC2", 0.20, pcbnew.B_Cu, (97.70, 49.95), (97.30, 49.95)),
    ("/USB_CC2", 0.20, pcbnew.B_Cu, (97.30, 49.95), (97.30, 47.65)),
    ("/USB_CC2", 0.20, pcbnew.B_Cu, (97.30, 47.65), (97.45, 47.65)),
    ("/GND", 0.30, pcbnew.F_Cu, (96.24, 48.6125), (95.80, 47.80)),
    ("/GND", 0.30, pcbnew.F_Cu, (95.80, 47.80), (93.45, 47.60)),
    ("/GND", 0.30, pcbnew.F_Cu, (93.45, 47.60), (93.45, 48.8625)),
    # Sub-GHz feed: keep the module-side pi section very short on B.Cu, then
    # make its sole signal-layer transition before the spring pocket.  The
    # F.Cu run remains on the narrow PCB bridge to A1 instead of entering the
    # open antenna notch.  Width is provisional until the production stack is
    # confirmed and the assembled matching network is measured.
    ("/SUBGHZ_RF_MOD", 0.36, pcbnew.B_Cu, (75.54, 63.75), (76.35, 64.70)),
    ("/SUBGHZ_RF_MOD", 0.36, pcbnew.B_Cu, (76.35, 64.70), (76.35, 66.00)),
    ("/SUBGHZ_RF_MOD", 0.36, pcbnew.B_Cu, (76.35, 66.00), (78.1875, 66.00)),
    ("/SUBGHZ_RF_ANT", 0.36, pcbnew.B_Cu, (80.0125, 66.00), (82.80, 65.95)),
    ("/SUBGHZ_RF_ANT", 0.36, pcbnew.B_Cu, (82.80, 65.95), (83.60, 66.50)),
    ("/SUBGHZ_RF_ANT", 0.36, pcbnew.F_Cu, (83.60, 66.50), (85.80, 66.50)),
    ("/SUBGHZ_RF_ANT", 0.36, pcbnew.F_Cu, (85.80, 66.50), (85.80, 69.25)),
    ("/SUBGHZ_RF_ANT", 0.36, pcbnew.F_Cu, (85.80, 69.25), (86.80, 70.45)),
    # Move the autorouted IR cathode branch below Y701 so the crystal loop can
    # remain short and via-free on B.Cu.
    ("/IR_LED_A3", 0.20, pcbnew.B_Cu, (32.25, 69.89), (33.70, 69.89)),
    ("/IR_LED_A3", 0.20, pcbnew.B_Cu, (33.70, 69.89), (33.70, 66.80)),
    ("/IR_LED_A3", 0.20, pcbnew.B_Cu, (33.70, 66.80), (36.80, 66.80)),
    ("/IR_LED_A3", 0.20, pcbnew.B_Cu, (36.80, 66.80), (37.8087, 67.8387)),
    # RTC crystal loop: local, via-free and kept on the component side.
    ("/RTC_OSCI", 0.20, pcbnew.B_Cu, (39.525, 71.405), (35.50, 70.75)),
    ("/RTC_OSCO", 0.20, pcbnew.B_Cu, (39.525, 70.135), (35.50, 68.25)),
)

VIAS: tuple[tuple[str, float, float, float, float], ...] = (
    ("/USB_CONN_P", 97.00, 50.95, 0.50, 0.30),
    ("/USB_CONN_P", 97.00, 51.95, 0.50, 0.30),
    ("/USB_CONN_N", 92.50, 48.25, 0.50, 0.30),
    ("/USB_CONN_N", 96.40, 51.45, 0.50, 0.30),
    ("/USB_CONN_N", 96.40, 52.45, 0.50, 0.30),
    ("/USB_CC2", 94.40, 50.90, 0.50, 0.30),
    ("/USB_CC2", 97.45, 47.65, 0.50, 0.30),
    ("/SUBGHZ_RF_ANT", 83.60, 66.50, 0.60, 0.30),
)

# Named rule areas make the two unavoidable U7 power-pin neckdowns, the
# low-current 5-V Kelvin branch and the fine-pitch USB bridge explicit.  Custom
# rules refer to these names, so the relaxations cannot leak into other routes.
RULE_AREAS: tuple[tuple[str, int, float, float, float, float], ...] = (
    ("U7_POWER_PIN_NECKDOWNS", pcbnew.B_Cu, 80.30, 42.60, 82.70, 45.15),
    ("U7_5V_SENSE_CORRIDOR", pcbnew.B_Cu, 79.40, 40.20, 84.80, 41.90),
    ("USB_J1_BRIDGE_F", pcbnew.F_Cu, 96.10, 50.60, 98.10, 52.75),
    ("USB_J1_BRIDGE_B", pcbnew.B_Cu, 96.10, 50.60, 98.10, 52.75),
)

REMOVED_SEGMENTS: tuple[
    tuple[str, float, int, tuple[float, float], tuple[float, float]], ...
] = (
    ("/IR_LED_A3", 0.20, pcbnew.B_Cu, (32.25, 69.89), (35.7574, 69.89)),
    ("/IR_LED_A3", 0.20, pcbnew.B_Cu, (35.7574, 69.89), (37.8087, 67.8387)),
    # Clear the intentionally reserved USB corridor.  These guarded
    # autorouter stubs are returned to the ratsnest for later digital routing.
    ("/SPI_SCK", 0.20, pcbnew.F_Cu, (82.20, 46.8875), (82.875, 47.5625)),
    ("/SPI_SCK", 0.20, pcbnew.F_Cu, (82.875, 47.5625), (83.4307, 47.5625)),
    ("/SPI_SCK", 0.20, pcbnew.B_Cu, (83.4307, 47.5625), (83.4307, 48.3678)),
    ("/SPI_MOSI", 0.20, pcbnew.F_Cu, (91.0527, 45.6077), (91.0527, 47.7885)),
    ("/SPI_MOSI", 0.20, pcbnew.F_Cu, (91.0527, 47.7885), (89.4929, 49.3483)),
    ("/SPI_MISO", 0.20, pcbnew.F_Cu, (93.235, 46.3509), (92.3744, 47.2115)),
    ("/SPI_MISO", 0.20, pcbnew.F_Cu, (92.3744, 47.2115), (92.3744, 51.8368)),
    ("/USB_CC2", 0.20, pcbnew.F_Cu, (94.95, 51.1375), (96.1623, 49.9252)),
    ("/USB_CONN_P", 0.20, pcbnew.F_Cu, (95.55, 50.00), (95.00, 49.45)),
    ("/USB_CONN_N", 0.20, pcbnew.F_Cu, (93.05, 48.8625), (92.70, 48.55)),
)

REMOVED_VIAS: tuple[tuple[str, float, float], ...] = (
    ("/SPI_SCK", 83.4307, 47.5625),
)

# These fanouts crossed the protected USB corridor in the guarded autorouter
# result.  Return the complete nets to the ratsnest instead of leaving partial
# or dangling stubs; they will be rerouted around the accepted USB pair.
CLEARED_NETS = frozenset(
    {
        "/SPI_SCK",
        "/SPI_MOSI",
        "/SPI_MISO",
        "/USB_CC2",
        "/NFC_DVDD",
        "/I2C_SCL",
        "/GPIO44_MCU",
        "/USER_BUTTON_A_N",
        "/USER_BUTTON_SELECT_N",
        "/USER_BUTTON_B_N",
        "/IR_LED_A1",
        "/GPIO43",
        "/NFC_LOADMOD",
        "/LF_DOUT_5V",
        # C404's corrected perpendicular pi-network placement occupies the
        # old display-supply autorouter corridor.  Return that low-speed net
        # to the ratsnest rather than leaving copper under the RF shunt.
        "/OLED_VCC",
    }
)


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def track_signature(track: pcbnew.PCB_TRACK) -> tuple[object, ...]:
    return (
        track.GetNetname(),
        track.GetLayer(),
        track.GetStart().x,
        track.GetStart().y,
        track.GetEnd().x,
        track.GetEnd().y,
        track.GetWidth(),
    )


def route_signature(
    net_name: str,
    width_mm: float,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[object, ...]:
    start_point = point(*start)
    end_point = point(*end)
    return (
        net_name,
        layer,
        start_point.x,
        start_point.y,
        end_point.x,
        end_point.y,
        pcbnew.FromMM(width_mm),
    )


def add_routes(board: pcbnew.BOARD) -> int:
    ordinary_tracks = [
        track
        for track in board.GetTracks()
        if isinstance(track, pcbnew.PCB_TRACK) and not isinstance(track, pcbnew.PCB_VIA)
    ]
    removed_signatures = {
        route_signature(net_name, width_mm, layer, start, end)
        for net_name, width_mm, layer, start, end in REMOVED_SEGMENTS
    }
    for track in ordinary_tracks:
        signature = track_signature(track)
        reverse = (
            signature[0],
            signature[1],
            signature[4],
            signature[5],
            signature[2],
            signature[3],
            signature[6],
        )
        if (
            track.GetNetname() in CLEARED_NETS
            or signature in removed_signatures
            or reverse in removed_signatures
        ):
            board.Delete(track)
    del ordinary_tracks

    for via in list(board.GetTracks()):
        if not isinstance(via, pcbnew.PCB_VIA):
            continue
        position = via.GetPosition()
        signature = (via.GetNetname(), position.x, position.y)
        removed_vias = {
            (net_name, point(x_mm, y_mm).x, point(x_mm, y_mm).y)
            for net_name, x_mm, y_mm in REMOVED_VIAS
        }
        if via.GetNetname() in CLEARED_NETS or signature in removed_vias:
            board.Delete(via)

    existing = {
        track_signature(track)
        for track in board.GetTracks()
        if isinstance(track, pcbnew.PCB_TRACK) and not isinstance(track, pcbnew.PCB_VIA)
    }
    added = 0
    for net_name, width_mm, layer, start, end in SEGMENTS:
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"Required critical net is missing: {net_name}")
        forward = route_signature(net_name, width_mm, layer, start, end)
        reverse = route_signature(net_name, width_mm, layer, end, start)
        if forward in existing or reverse in existing:
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(width_mm))
        track.SetLayer(layer)
        track.SetNet(net)
        board.Add(track)
        existing.add(forward)
        added += 1

    existing_vias = {
        (via.GetNetname(), via.GetPosition().x, via.GetPosition().y)
        for via in board.GetTracks()
        if isinstance(via, pcbnew.PCB_VIA)
    }
    for net_name, x_mm, y_mm, diameter_mm, drill_mm in VIAS:
        position = point(x_mm, y_mm)
        signature = (net_name, position.x, position.y)
        if signature in existing_vias:
            continue
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"Required via net is missing: {net_name}")
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(position)
        via.SetWidth(pcbnew.FromMM(diameter_mm))
        via.SetDrill(pcbnew.FromMM(drill_mm))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(net)
        board.Add(via)
        existing_vias.add(signature)
        added += 1
    return added


def add_rule_areas(board: pcbnew.BOARD) -> int:
    existing = {zone.GetZoneName() for zone in board.Zones()}
    added = 0
    for name, layer, left, top, right, bottom in RULE_AREAS:
        if name in existing:
            continue
        area = pcbnew.ZONE(board)
        area.SetZoneName(name)
        area.SetLayer(layer)
        area.SetIsRuleArea(True)
        area.SetDoNotAllowZoneFills(False)
        area.SetDoNotAllowTracks(False)
        area.SetDoNotAllowVias(False)
        area.SetDoNotAllowPads(False)
        area.SetDoNotAllowFootprints(False)
        outline = area.Outline()
        outline.NewOutline()
        for x_mm, y_mm in (
            (left, top),
            (right, top),
            (right, bottom),
            (left, bottom),
        ):
            outline.Append(point(x_mm, y_mm))
        board.Add(area)
        existing.add(name)
        added += 1
    return added


def orient_fixed_routing_parts(board: pcbnew.BOARD) -> None:
    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}

    def place(reference: str, side: str, x_mm: float, y_mm: float, rotation: float) -> pcbnew.FOOTPRINT:
        footprint = footprints.get(reference)
        if footprint is None:
            raise RuntimeError(f"{reference} is missing")
        target_layer = pcbnew.F_Cu if side == "F" else pcbnew.B_Cu
        if footprint.GetLayer() != target_layer:
            footprint.Flip(footprint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        footprint.SetPosition(point(x_mm, y_mm))
        footprint.SetOrientationDegrees(rotation)
        if footprint.GetLayer() != target_layer:
            raise RuntimeError(f"Failed to place {reference} on {side}.Cu")
        return footprint

    resistor = footprints.get("R405")
    if resistor is None:
        raise RuntimeError("R405 is missing")
    resistor.SetOrientationDegrees(0.0)
    pads = {pad.GetNumber(): pcbnew.ToMM(pad.GetPosition().x) for pad in resistor.Pads()}
    if not pads["1"] < pads["2"]:
        raise RuntimeError("R405 pad 1 must face U3 and pad 2 must face the antenna")

    input_shunt = footprints.get("C403")
    output_shunt = footprints.get("C404")
    if input_shunt is None or output_shunt is None:
        raise RuntimeError("C403/C404 Sub-GHz shunt footprints are missing")
    input_shunt.SetOrientationDegrees(180.0)
    # Rotate the output shunt perpendicular to the feed.  Its RF pad now sits
    # directly on the main line while the ground pad branches upward, rather
    # than forcing the antenna net to cross the ground land.
    output_shunt.SetOrientationDegrees(90.0)
    output_shunt.SetPosition(point(82.80, 65.00))

    usb_n = footprints.get("R201")
    usb_p = footprints.get("R202")
    if usb_n is None or usb_p is None:
        raise RuntimeError("R201/R202 USB series footprints are missing")
    for resistor, x_mm in ((usb_n, 84.30), (usb_p, 86.56)):
        resistor.SetPosition(point(x_mm, 48.15))
        resistor.SetOrientationDegrees(90.0)
        pads = {pad.GetNumber(): pcbnew.ToMM(pad.GetPosition().y) for pad in resistor.Pads()}
        if not pads["2"] < pads["1"]:
            raise RuntimeError(f"{resistor.GetReference()} pad 2 must face the MCU")

    place("U16", "F", 93.45, 50.00, 270.0)
    # Open the standard-via window for CC2 without shrinking the project via
    # limits.  These moves are only 0.05-0.10 mm and retain the local USB power
    # decoupling topology.  A dedicated 0.20-mm local clearance rule covers the
    # short centre-gap escape between C103/C104.
    place("C106", "B", 94.15, 49.65, 0.0)
    place("C103", "B", 94.15, 52.05, 0.0)
    cc1_pull_down = place("R101", "B", 102.295, 70.225, 90.0)
    cc2_pull_down = place("R102", "F", 96.24, 47.70, 270.0)
    cc1_pads = {pad.GetNumber(): pcbnew.ToMM(pad.GetPosition().y) for pad in cc1_pull_down.Pads()}
    cc2_pads = {pad.GetNumber(): pcbnew.ToMM(pad.GetPosition().y) for pad in cc2_pull_down.Pads()}
    if not cc1_pads["2"] < cc1_pads["1"]:
        raise RuntimeError("R101 pad 1 must face the lower card edge")
    if not cc2_pads["1"] < cc2_pads["2"]:
        raise RuntimeError("R102 pad 1 must face the upper card edge")

    nfc_dvdd = footprints.get("C314")
    if nfc_dvdd is None:
        raise RuntimeError("C314 NFC_DVDD capacitor is missing")
    nfc_dvdd.SetPosition(point(89.845, 47.025))
    nfc_dvdd.SetOrientationDegrees(0.0)



def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=hardware_dir / "PocketLab-Card-routed.kicad_pcb",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=hardware_dir / "PocketLab-Card-routing-progress.kicad_pcb",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    main_board = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input board is missing: {input_path}")
    if output_path == main_board:
        raise RuntimeError("Refusing to overwrite the main PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    print(f"Loading routing staging board: {input_path}", flush=True)
    board = pcbnew.LoadBoard(str(input_path))
    print("Orienting fixed routing elements", flush=True)
    orient_fixed_routing_parts(board)
    print("Adding local critical tracks", flush=True)
    added = add_routes(board)
    areas_added = add_rule_areas(board)
    title = board.GetTitleBlock()
    title.SetRevision("ROUTING_DRAFT")
    title.SetComment(1, "4-layer, 1.2 mm; routing in progress")
    title.SetComment(2, "ROUTING IN PROGRESS; not for production")
    board.SetTitleBlock(title)
    print(f"Saving routing checkpoint: {output_path}", flush=True)
    pcbnew.SaveBoard(str(output_path), board)

    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(f"Saved critical-routing checkpoint: {output_path}")
    print(
        f"Added {added} reviewed local track segments and {areas_added} rule areas; "
        "R405 now faces U3 -> antenna"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
