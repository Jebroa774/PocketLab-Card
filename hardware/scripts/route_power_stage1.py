"""Route the first local USB-fused charger-input power cluster.

This deterministic pass connects the fuse output, surge clamp, the two local
input capacitors and BQ25895 VBUS pin.  It deliberately does not attempt the
connector-to-fuse VBUS_USB path or the battery/VSYS trunks; those need their
own reviewed high-current geometry.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

import route_lf_global as router


NET = "/VBUS_FUSED"
LAYER = pcbnew.B_Cu
RULE_AREA_NAME = "U5_POWER_PIN_NECKDOWNS"
RULE_AREA = (88.40, 48.35, 92.75, 52.65)

# The 0.50-mm path around the USB data corridor was found with the same
# geometry/clearance engine used by route_lf_global.py, then frozen here so
# this safety-critical power cluster remains reproducible and reviewable.
SEGMENTS: tuple[tuple[float, tuple[float, float], tuple[float, float]], ...] = (
    (0.60, (93.50, 47.10), (91.60, 47.10)),  # F1.2 -> D101.1
    (0.50, (93.50, 47.10), (93.25, 47.35)),
    (0.50, (93.25, 47.35), (92.25, 47.35)),
    (0.50, (92.25, 47.35), (91.75, 47.85)),
    (0.50, (91.75, 47.85), (91.75, 48.60)),
    (0.50, (91.75, 48.60), (92.50, 49.35)),
    (0.50, (92.50, 49.35), (92.75, 49.35)),
    (0.50, (92.75, 49.35), (93.20, 49.65)),  # -> C106.1
    (0.60, (93.20, 49.65), (93.20, 52.05)),  # C106.1 -> C103.1
    (0.20, (91.6375, 49.75), (92.65, 49.75)),  # U5.13 package neck
    (0.50, (92.65, 49.75), (93.20, 49.65)),
)

U16_SEGMENTS: tuple[
    tuple[int, float, tuple[float, float], tuple[float, float]], ...
] = (
    (pcbnew.F_Cu, 0.50, (93.45, 51.1375), (93.45, 52.3375)),
    (pcbnew.F_Cu, 0.50, (93.45, 52.3375), (93.25, 52.5375)),
    (pcbnew.B_Cu, 0.50, (93.25, 52.5375), (93.20, 52.05)),
)
U16_VIA = (93.25, 52.5375)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return router.point(*position)


def segment_signature(
    layer: int,
    width_mm: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[object, ...]:
    first = point(start)
    second = point(end)
    endpoints = sorted(((first.x, first.y), (second.x, second.y)))
    return (
        NET,
        layer,
        endpoints[0],
        endpoints[1],
        pcbnew.FromMM(width_mm),
    )


def track_signature(track: pcbnew.PCB_TRACK) -> tuple[object, ...]:
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


def add_rule_area(board: pcbnew.BOARD) -> int:
    if any(zone.GetZoneName() == RULE_AREA_NAME for zone in board.Zones()):
        return 0
    left, top, right, bottom = RULE_AREA
    area = pcbnew.ZONE(board)
    area.SetZoneName(RULE_AREA_NAME)
    area.SetLayer(LAYER)
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


def add_segments(board: pcbnew.BOARD) -> int:
    net = board.FindNet(NET)
    if net is None:
        raise RuntimeError(f"Required power net is missing: {NET}")
    edge = router.board_rect(board)
    obstacles = router.existing_obstacles(board)
    existing = {
        track_signature(item)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_TRACK)
        and not isinstance(item, pcbnew.PCB_VIA)
    }
    added = 0
    all_segments = tuple((LAYER, width, start, end) for width, start, end in SEGMENTS)
    all_segments += U16_SEGMENTS
    for layer, width_mm, start, end in all_segments:
        signature = segment_signature(layer, width_mm, start, end)
        if signature in existing:
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
        existing.add(signature)
        added += 1

    existing_vias = {
        (item.GetPosition().x, item.GetPosition().y)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA) and item.GetNetname() == NET
    }
    via_point = point(U16_VIA)
    if (via_point.x, via_point.y) not in existing_vias:
        router.VIA_DIAMETER_MM = 0.80
        if not router.signal_via_is_clear(
            net_name=NET,
            position=U16_VIA,
            endpoint_pad_ids=set(),
            edge=edge,
            obstacles=obstacles,
        ):
            raise RuntimeError("Reviewed U16 VBUS_FUSED via is blocked")
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(via_point)
        via.SetWidth(pcbnew.FromMM(0.80))
        via.SetDrill(pcbnew.FromMM(0.40))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(net)
        via.SetLocked(True)
        board.Add(via)
    return added


def validate(board: pcbnew.BOARD) -> None:
    endpoints = {
        name: router.pad_by_reference(board, reference, pin)
        for name, reference, pin in (
            ("fuse", "F1", "2"),
            ("clamp", "D101", "1"),
            ("input_cap", "C106", "1"),
            ("bulk_cap", "C103", "1"),
            ("charger", "U5", "13"),
            ("usb_protector", "U16", "5"),
        )
    }
    anchor = endpoints["fuse"]
    for name, pad in endpoints.items():
        if pad.GetNetname() != NET:
            raise RuntimeError(f"{name} endpoint net mismatch")
        if not router.already_connected(board, anchor, pad):
            raise RuntimeError(f"Serialized PCB lost {NET} connectivity to {name}")
    if not any(zone.GetZoneName() == RULE_AREA_NAME for zone in board.Zones()):
        raise RuntimeError("U5 power-pin neckdown rule area is missing")


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
    tracks = add_segments(board)
    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded)
    print(
        f"Saved charger-input power stage: {output_path}; "
        f"segments={tracks}; rule_areas={areas}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
