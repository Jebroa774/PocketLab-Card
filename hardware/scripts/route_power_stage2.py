"""Route the local BQ25895 CELL_POS output and its two buffer capacitors.

Run after route_power_stage1.py.  The two 0.5-mm-pitch charger pins use short
0.20-mm package escapes, merge immediately, and widen to 0.50 mm.  Two
0.80/0.40-mm vias carry the wide bridge around C104's intervening GND pad.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

import route_lf_global as router


NET = "/CELL_POS"
RULE_AREA_NAME = "U5_POWER_PIN_NECKDOWNS"
SEGMENTS: tuple[
    tuple[int, float, tuple[float, float], tuple[float, float]], ...
] = (
    (pcbnew.B_Cu, 0.20, (90.45, 51.9375), (90.45, 53.00)),
    (pcbnew.B_Cu, 0.20, (89.95, 51.9375), (89.95, 53.00)),
    (pcbnew.B_Cu, 0.20, (90.45, 53.00), (89.95, 53.00)),
    (pcbnew.B_Cu, 0.50, (89.95, 53.00), (89.95, 53.50)),
    (pcbnew.B_Cu, 0.50, (89.95, 53.50), (89.75, 54.10)),
    (pcbnew.B_Cu, 0.50, (89.75, 54.10), (89.75, 54.70)),
    (pcbnew.B_Cu, 0.50, (89.75, 54.70), (90.55, 55.50)),
    (pcbnew.F_Cu, 0.50, (90.55, 55.50), (91.30, 55.50)),
    (pcbnew.F_Cu, 0.50, (91.30, 55.50), (91.55, 55.25)),
    (pcbnew.F_Cu, 0.50, (91.55, 55.25), (91.80, 55.25)),
    (pcbnew.F_Cu, 0.50, (91.80, 55.25), (92.05, 55.00)),
    (pcbnew.F_Cu, 0.50, (92.05, 55.00), (92.80, 55.00)),
    (pcbnew.F_Cu, 0.50, (92.80, 55.00), (93.35, 54.70)),
    (pcbnew.B_Cu, 0.50, (93.35, 54.70), (93.35, 54.10)),
    # Reuse the C104 bridge via for the preferred 0.80-mm battery-positive
    # trunk instead of adding a second transition beside the capacitor.
    (pcbnew.F_Cu, 0.80, (93.35, 54.70), (96.85, 59.20)),
    (pcbnew.F_Cu, 0.80, (96.85, 59.20), (96.85, 60.95)),
    (pcbnew.F_Cu, 0.80, (96.85, 60.95), (98.10, 62.20)),
    (pcbnew.F_Cu, 0.80, (98.10, 62.20), (98.10, 62.45)),
    (pcbnew.F_Cu, 0.80, (98.10, 62.45), (98.35, 62.70)),
    (pcbnew.F_Cu, 0.80, (98.35, 62.70), (98.35, 62.95)),
    (pcbnew.F_Cu, 0.80, (98.35, 62.95), (98.90, 64.05)),
    (pcbnew.B_Cu, 0.80, (98.90, 64.05), (100.70, 65.85)),
    (pcbnew.B_Cu, 0.80, (100.70, 65.85), (101.10, 65.85)),
)
VIAS = ((90.55, 55.50), (93.35, 54.70), (98.90, 64.05))


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return router.point(*position)


def track_signature(
    net_name: str,
    layer: int,
    width_mm: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[object, ...]:
    first = point(start)
    second = point(end)
    endpoints = sorted(((first.x, first.y), (second.x, second.y)))
    return (
        net_name,
        layer,
        endpoints[0],
        endpoints[1],
        pcbnew.FromMM(width_mm),
    )


def existing_track_signature(track: pcbnew.PCB_TRACK) -> tuple[object, ...]:
    endpoints = sorted(
        (
            (track.GetStart().x, track.GetStart().y),
            (track.GetEnd().x, track.GetEnd().y),
        )
    )
    return (
        track.GetNetname(),
        track.GetLayer(),
        endpoints[0],
        endpoints[1],
        track.GetWidth(),
    )


def add_routes(board: pcbnew.BOARD) -> tuple[int, int]:
    if not any(zone.GetZoneName() == RULE_AREA_NAME for zone in board.Zones()):
        raise RuntimeError("Run route_power_stage1.py before this pass")
    net = board.FindNet(NET)
    if net is None:
        raise RuntimeError(f"Required power net is missing: {NET}")
    edge = router.board_rect(board)
    obstacles = router.existing_obstacles(board)
    existing_tracks = {
        existing_track_signature(item)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_TRACK)
        and not isinstance(item, pcbnew.PCB_VIA)
    }
    added_tracks = 0
    for layer, width_mm, start, end in SEGMENTS:
        signature = track_signature(NET, layer, width_mm, start, end)
        if signature in existing_tracks:
            continue
        if not router.track_segment_is_clear(
            net_name=NET,
            layer=layer,
            start=start,
            end=end,
            width_mm=width_mm,
            source_pads=set(),
            edge=edge,
            obstacles=obstacles,
        ):
            raise RuntimeError(
                f"Reviewed {NET} segment is blocked: {start} -> {end} at {width_mm} mm"
            )
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
                NET, "track", (start, end, width_mm / 2.0, layer), track
            )
        )
        existing_tracks.add(signature)
        added_tracks += 1

    existing_vias = {
        (item.GetPosition().x, item.GetPosition().y)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA) and item.GetNetname() == NET
    }
    added_vias = 0
    router.VIA_DIAMETER_MM = 0.80
    for position in VIAS:
        via_point = point(position)
        if (via_point.x, via_point.y) in existing_vias:
            continue
        if not router.signal_via_is_clear(
            net_name=NET,
            position=position,
            endpoint_pad_ids=set(),
            edge=edge,
            obstacles=obstacles,
        ):
            raise RuntimeError(f"Reviewed {NET} via is blocked at {position}")
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(via_point)
        via.SetWidth(pcbnew.FromMM(0.80))
        via.SetDrill(pcbnew.FromMM(0.40))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(net)
        via.SetLocked(True)
        board.Add(via)
        obstacles.append(
            router.CopperObstacle(NET, "via", (position, 0.40), via)
        )
        existing_vias.add((via_point.x, via_point.y))
        added_vias += 1
    return added_tracks, added_vias


def validate(board: pcbnew.BOARD) -> None:
    pads = [
        router.pad_by_reference(board, reference, pin)
        for reference, pin in (
            ("U5", "2"),
            ("U5", "3"),
            ("C121", "1"),
            ("C104", "1"),
            ("J4", "1"),
        )
    ]
    if any(pad.GetNetname() != NET for pad in pads):
        raise RuntimeError("CELL_POS endpoint net mismatch")
    if any(not router.already_connected(board, pads[0], pad) for pad in pads[1:]):
        raise RuntimeError("Serialized PCB lost local CELL_POS connectivity")


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
    tracks, vias = add_routes(board)
    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded)
    print(
        f"Saved local CELL_POS stage: {output_path}; segments={tracks}; vias={vias}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
