"""Route the protected battery-negative MOSFET current path.

The J4.2 escape deliberately places its first via outside the connector land
to avoid solder wicking.  CELL_NEG then crosses the dense lower-right field on
F.Cu, returns to B.Cu before Q2, and enters the discharge MOSFET with 0.50-mm
copper.  Q2's three 0.64-mm-pitch source pads need a short reviewed 0.20-mm
local tie; the drain-to-drain BAT_FET_MID connection is 0.80 mm wide.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

import route_lf_global as router


CELL_NEG = "/CELL_NEG"
FET_MID = "/BAT_FET_MID"
RULE_AREA_NAME = "Q2_CELL_NEG_PIN_NECKDOWN"
RULE_AREA = (96.15, 70.35, 97.15, 72.45)

SEGMENTS: tuple[
    tuple[str, int, float, tuple[float, float], tuple[float, float]], ...
] = (
    (CELL_NEG, pcbnew.B_Cu, 0.50, (103.10, 65.85), (104.25, 65.75)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (104.25, 65.75), (97.25, 65.75)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (97.25, 65.75), (97.00, 65.50)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (97.00, 65.50), (96.75, 65.50)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (96.75, 65.50), (96.25, 65.00)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (96.25, 65.00), (95.50, 65.00)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (95.50, 65.00), (95.25, 64.75)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (95.25, 64.75), (95.00, 64.75)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (95.00, 64.75), (94.35, 64.35)),
    # Drop to B.Cu only long enough to pass above SW5, then cross its two
    # mechanical holes on F.Cu with explicit 0.25-mm hole clearance.
    (CELL_NEG, pcbnew.B_Cu, 0.50, (94.35, 64.35), (94.35, 67.60)),
    (CELL_NEG, pcbnew.B_Cu, 0.50, (94.35, 67.60), (93.10, 68.85)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (93.10, 68.85), (93.35, 69.10)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (93.35, 69.10), (93.35, 69.60)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (93.35, 69.60), (94.10, 70.35)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (94.10, 70.35), (94.85, 70.35)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (94.85, 70.35), (95.35, 69.85)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (95.35, 69.85), (95.35, 69.60)),
    (CELL_NEG, pcbnew.F_Cu, 0.50, (95.35, 69.60), (95.60, 69.35)),
    (CELL_NEG, pcbnew.B_Cu, 0.50, (95.60, 69.35), (96.35, 70.10)),
    (CELL_NEG, pcbnew.B_Cu, 0.50, (96.35, 70.10), (96.35, 70.35)),
    (CELL_NEG, pcbnew.B_Cu, 0.50, (96.35, 70.35), (96.64, 70.83)),
    (CELL_NEG, pcbnew.B_Cu, 0.20, (96.64, 70.83), (96.64, 72.13)),
    (FET_MID, pcbnew.B_Cu, 0.80, (94.815, 71.80), (91.035, 71.80)),
)
VIAS: tuple[tuple[float, float], ...] = (
    (104.25, 65.75),
    (94.35, 64.35),
    (93.10, 68.85),
    (95.60, 69.35),
)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return router.point(*position)


def add_rule_area(board: pcbnew.BOARD) -> int:
    if any(zone.GetZoneName() == RULE_AREA_NAME for zone in board.Zones()):
        return 0
    left, top, right, bottom = RULE_AREA
    area = pcbnew.ZONE(board)
    area.SetZoneName(RULE_AREA_NAME)
    area.SetLayer(pcbnew.B_Cu)
    area.SetIsRuleArea(True)
    area.SetDoNotAllowZoneFills(False)
    area.SetDoNotAllowTracks(False)
    area.SetDoNotAllowVias(False)
    area.SetDoNotAllowPads(False)
    area.SetDoNotAllowFootprints(False)
    outline = area.Outline()
    outline.NewOutline()
    for position in ((left, top), (right, top), (right, bottom), (left, bottom)):
        outline.Append(point(position))
    board.Add(area)
    return 1


def track_signature(
    net_name: str,
    layer: int,
    width_mm: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[object, ...]:
    first = point(start)
    second = point(end)
    ends = sorted(((first.x, first.y), (second.x, second.y)))
    return net_name, layer, ends[0], ends[1], pcbnew.FromMM(width_mm)


def existing_track_signature(track: pcbnew.PCB_TRACK) -> tuple[object, ...]:
    ends = sorted(
        (
            (track.GetStart().x, track.GetStart().y),
            (track.GetEnd().x, track.GetEnd().y),
        )
    )
    return track.GetNetname(), track.GetLayer(), ends[0], ends[1], track.GetWidth()


def add_routes(board: pcbnew.BOARD) -> tuple[int, int]:
    edge = router.board_rect(board)
    obstacles = router.existing_obstacles(board)
    existing_tracks = {
        existing_track_signature(item)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_TRACK)
        and not isinstance(item, pcbnew.PCB_VIA)
    }
    tracks_added = 0
    for net_name, layer, width_mm, start, end in SEGMENTS:
        signature = track_signature(net_name, layer, width_mm, start, end)
        if signature in existing_tracks:
            continue
        if not router.track_segment_is_clear(
            net_name=net_name,
            layer=layer,
            start=start,
            end=end,
            width_mm=width_mm,
            source_pads=set(),
            edge=edge,
            obstacles=obstacles,
        ):
            raise RuntimeError(
                f"Reviewed {net_name} segment is blocked: {start} -> {end} at {width_mm} mm"
            )
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"Required power net is missing: {net_name}")
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(start))
        track.SetEnd(point(end))
        track.SetWidth(pcbnew.FromMM(width_mm))
        track.SetLayer(layer)
        track.SetNet(net)
        track.SetLocked(True)
        board.Add(track)
        obstacles.append(
            router.CopperObstacle(
                net_name, "track", (start, end, width_mm / 2.0, layer), track
            )
        )
        existing_tracks.add(signature)
        tracks_added += 1

    existing_vias = {
        (item.GetPosition().x, item.GetPosition().y)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA) and item.GetNetname() == CELL_NEG
    }
    router.VIA_DIAMETER_MM = 0.80
    vias_added = 0
    for position in VIAS:
        via_position = point(position)
        if (via_position.x, via_position.y) in existing_vias:
            continue
        if not router.signal_via_is_clear(
            net_name=CELL_NEG,
            position=position,
            endpoint_pad_ids=set(),
            edge=edge,
            obstacles=obstacles,
        ):
            raise RuntimeError(f"Reviewed CELL_NEG via is blocked at {position}")
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(via_position)
        via.SetWidth(pcbnew.FromMM(0.80))
        via.SetDrill(pcbnew.FromMM(0.40))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(board.FindNet(CELL_NEG))
        via.SetLocked(True)
        board.Add(via)
        obstacles.append(router.CopperObstacle(CELL_NEG, "via", (position, 0.40), via))
        existing_vias.add((via_position.x, via_position.y))
        vias_added += 1
    return tracks_added, vias_added


def validate(board: pcbnew.BOARD) -> None:
    cell_pads = [
        router.pad_by_reference(board, reference, pin)
        for reference, pin in (("J4", "2"), ("Q2", "1"), ("Q2", "2"), ("Q2", "3"))
    ]
    if any(pad.GetNetname() != CELL_NEG for pad in cell_pads):
        raise RuntimeError("CELL_NEG endpoint net mismatch")
    if any(not router.already_connected(board, cell_pads[0], pad) for pad in cell_pads[1:]):
        raise RuntimeError("Serialized PCB lost CELL_NEG power-path connectivity")
    q2_mid = router.pad_by_reference(board, "Q2", "5")
    q3_mid = router.pad_by_reference(board, "Q3", "5")
    if not router.already_connected(board, q2_mid, q3_mid):
        raise RuntimeError("Serialized PCB lost BAT_FET_MID connectivity")
    connector_pad = router.pad_by_reference(board, "J4", "2")
    connector_box = router.rect_of(connector_pad)
    for item in board.GetTracks():
        if not isinstance(item, pcbnew.PCB_VIA) or item.GetNetname() != CELL_NEG:
            continue
        if connector_box.contains(router.xy(item.GetPosition())):
            raise RuntimeError("CELL_NEG via must remain outside the J4.2 solder land")
    if not any(zone.GetZoneName() == RULE_AREA_NAME for zone in board.Zones()):
        raise RuntimeError("Q2 CELL_NEG neckdown rule area is missing")


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    areas = add_rule_area(board)
    tracks, vias = add_routes(board)
    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded)
    print(
        f"Saved battery-negative power stage: {output_path}; "
        f"segments={tracks}; vias={vias}; rule_areas={areas}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
