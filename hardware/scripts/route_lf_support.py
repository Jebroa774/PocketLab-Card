"""Route the local LF-RFID load-switch, power and return branches.

This pass follows ``route_lf_rfid.py``.  It keeps the hand-solderable U17
support island compact, uses ordinary tented through vias outside SMD lands,
and carries LF_5V on 0.50-mm outer copper to U4, the 4-MHz oscillator and its
decoupler.  The upstream +5V_RAW, translator and MCU control branches remain
available for the later global digital/power routing pass.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


F = pcbnew.F_Cu
B = pcbnew.B_Cu

SEGMENTS: tuple[
    tuple[str, float, int, tuple[float, float], tuple[float, float]], ...
] = (
    # U17 quick-output-discharge and default-off enable support.
    ("/LF_QOD", 0.25, F, (41.3375, 55.5000), (42.8375, 55.5000)),
    ("/LF_RFID_EN", 0.20, F, (39.6625, 56.1500), (38.8000, 56.1500)),
    ("/LF_RFID_EN", 0.20, F, (38.8000, 56.1500), (37.4125, 55.5000)),
    # Local LF_5V generation, both decouplers and the U4-side transition.
    ("/LF_5V", 0.20, F, (41.3375, 54.8500), (42.0000, 54.2000)),
    ("/LF_5V", 0.50, F, (42.0000, 54.2000), (44.6625, 54.2000)),
    ("/LF_5V", 0.50, F, (44.6625, 54.2000), (44.6625, 55.5000)),
    ("/LF_5V", 0.50, F, (44.6625, 55.5000), (45.4500, 56.2875)),
    ("/LF_5V", 0.50, F, (45.4500, 56.2875), (45.4500, 58.8000)),
    ("/LF_5V", 0.50, F, (45.4500, 58.8000), (45.4500, 60.1000)),
    ("/LF_5V", 0.50, F, (45.4500, 60.1000), (41.7000, 60.1000)),
    ("/LF_5V", 0.50, F, (41.7000, 60.1000), (41.7000, 58.4900)),
    ("/LF_5V", 0.50, F, (39.9500, 59.5000), (41.7000, 58.4900)),
    ("/LF_5V", 0.50, B, (41.7000, 58.4900), (40.5250, 58.4900)),
    # Front-side distribution below the NFC loop.  Two separate far-side vias
    # avoid threading 0.50-mm power copper between Y501/C513 ground pads.
    ("/LF_5V", 0.50, F, (45.4500, 60.1000), (46.8000, 60.1000)),
    ("/LF_5V", 0.50, F, (46.8000, 60.1000), (46.8000, 53.1000)),
    ("/LF_5V", 0.50, F, (46.8000, 53.1000), (63.0000, 53.1000)),
    ("/LF_5V", 0.50, F, (63.0000, 53.1000), (63.0000, 52.9000)),
    ("/LF_5V", 0.50, B, (63.0000, 52.9000), (61.7500, 53.9250)),
    ("/LF_5V", 0.50, B, (61.7500, 53.9250), (61.7500, 55.4750)),
    ("/LF_5V", 0.50, F, (63.0000, 53.1000), (67.0000, 53.1000)),
    ("/LF_5V", 0.50, F, (67.0000, 53.1000), (67.0000, 54.7000)),
    ("/LF_5V", 0.50, B, (67.0000, 54.7000), (65.9000, 54.7000)),
)

VIAS: tuple[tuple[str, float, float, float, float], ...] = (
    ("/LF_5V", 41.7000, 58.4900, 0.60, 0.30),
    ("/LF_5V", 63.0000, 52.9000, 0.70, 0.30),
    ("/LF_5V", 67.0000, 54.7000, 0.70, 0.30),
)

LOCAL_NETS = frozenset({"/LF_QOD", "/LF_5V"})
RULE_AREA_NAME = "U17_LF5V_NECKDOWN"


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def add_routes(board: pcbnew.BOARD) -> int:
    # QOD and LF_5V are owned by this deterministic pass.  EN/GND are shared
    # global nets, so only stale copper physically touching the moved support
    # footprints was removed by the placement merge.
    for item in list(board.GetTracks()):
        if item.GetNetname() in LOCAL_NETS:
            board.Delete(item)

    added = 0
    for net_name, width_mm, layer, start, end in SEGMENTS:
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"Required LF support net is missing: {net_name}")
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(width_mm))
        track.SetLayer(layer)
        track.SetNet(net)
        board.Add(track)
        added += 1

    for net_name, x_mm, y_mm, diameter_mm, drill_mm in VIAS:
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"Required LF support via net is missing: {net_name}")
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(x_mm, y_mm))
        via.SetWidth(pcbnew.FromMM(diameter_mm))
        via.SetDrill(pcbnew.FromMM(drill_mm))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(net)
        board.Add(via)
        added += 1
    return added


def add_rule_area(board: pcbnew.BOARD) -> int:
    if any(zone.GetZoneName() == RULE_AREA_NAME for zone in board.Zones()):
        return 0
    area = pcbnew.ZONE(board)
    area.SetZoneName(RULE_AREA_NAME)
    area.SetLayer(pcbnew.F_Cu)
    area.SetIsRuleArea(True)
    area.SetDoNotAllowZoneFills(False)
    area.SetDoNotAllowTracks(False)
    area.SetDoNotAllowVias(False)
    area.SetDoNotAllowPads(False)
    area.SetDoNotAllowFootprints(False)
    outline = area.Outline()
    outline.NewOutline()
    for x_mm, y_mm in (
        (41.00, 53.95),
        (42.25, 53.95),
        (42.25, 55.10),
        (41.00, 55.10),
    ):
        outline.Append(point(x_mm, y_mm))
    board.Add(area)
    return 1


def validate(board: pcbnew.BOARD) -> None:
    expected_vias = {(net, point(x, y).x, point(x, y).y) for net, x, y, _, _ in VIAS}
    actual_vias = {
        (item.GetNetname(), item.GetPosition().x, item.GetPosition().y)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA)
    }
    missing = expected_vias - actual_vias
    if missing:
        raise RuntimeError(f"LF support vias were not serialized: {sorted(missing)}")


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    main_board = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == main_board:
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    added = add_routes(board)
    added += add_rule_area(board)
    validate(board)
    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded)
    print(f"Saved LF support routed PCB: {output_path}; added_items={added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
