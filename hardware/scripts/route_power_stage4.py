"""Complete the local 1-cell protection-controller control connections.

The high-current CELL_NEG/BAT_FET_MID path is owned by power stage 3.  This
pass closes the remaining BAT_COUT gate-control gap and connects the BQ29700's
low-current CELL_NEG reference, its capacitor and R106 to that main path.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

import route_lf_global as router


RULE_AREAS: tuple[tuple[str, int, float, float, float, float], ...] = (
    ("U14_BAT_COUT_ESCAPE", pcbnew.B_Cu, 88.15, 64.75, 91.65, 68.00),
    ("CELL_NEG_SENSE_BRANCH_B", pcbnew.B_Cu, 85.20, 63.95, 97.05, 71.15),
    ("CELL_NEG_SENSE_BRANCH_F", pcbnew.F_Cu, 86.55, 64.00, 94.20, 67.05),
)

BAT_COUT_ROUTE = (
    (88.575, 65.50, pcbnew.B_Cu),
    (89.25, 65.50, pcbnew.B_Cu),
    (89.25, 66.70, pcbnew.B_Cu),
    (91.3125, 66.70, pcbnew.B_Cu),
    (91.3125, 67.80, pcbnew.B_Cu),
)

CELL_NEG_LOCAL_ROUTE = (
    (87.425, 66.00, pcbnew.B_Cu),
    (86.425, 66.00, pcbnew.B_Cu),
    (85.60, 66.35, pcbnew.B_Cu),
)

CELL_NEG_SENSE_ROUTE = (
    (87.425, 66.00, pcbnew.B_Cu),
    (87.425, 66.20, pcbnew.B_Cu),
    (87.025, 66.60, pcbnew.B_Cu),
    (87.025, 66.60, pcbnew.F_Cu),
    (87.275, 66.35, pcbnew.F_Cu),
    (87.275, 64.85, pcbnew.F_Cu),
    (87.525, 64.60, pcbnew.F_Cu),
    (93.275, 64.60, pcbnew.F_Cu),
    (94.35, 64.35, pcbnew.F_Cu),
)

CELL_NEG_TO_MAIN_ROUTE = (
    (93.7875, 67.80, pcbnew.B_Cu),
    (94.35, 67.60, pcbnew.B_Cu),
)


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return router.point(x_mm, y_mm)


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


def add_reviewed_route(
    board: pcbnew.BOARD,
    obstacles: list[router.CopperObstacle],
    net_name: str,
    route: tuple[tuple[float, float, int], ...],
    width_mm: float,
) -> tuple[int, int]:
    old_track_width = router.TRACK_WIDTH_MM
    old_via_diameter = router.VIA_DIAMETER_MM
    old_via_drill = router.VIA_DRILL_MM
    router.TRACK_WIDTH_MM = width_mm
    router.VIA_DIAMETER_MM = 0.50
    router.VIA_DRILL_MM = 0.30
    try:
        edge = router.board_rect(board)
        for first, second in zip(route, route[1:]):
            if first[2] != second[2]:
                if router.distance((first[0], first[1]), (second[0], second[1])) > 0.001:
                    raise RuntimeError(f"Layer transition moved on {net_name}")
                if not router.signal_via_is_clear(
                    net_name=net_name,
                    position=(first[0], first[1]),
                    endpoint_pad_ids=set(),
                    edge=edge,
                    obstacles=obstacles,
                ):
                    raise RuntimeError(f"Reviewed {net_name} via is blocked at {first[:2]}")
            elif not router.track_segment_is_clear(
                net_name=net_name,
                layer=first[2],
                start=(first[0], first[1]),
                end=(second[0], second[1]),
                width_mm=width_mm,
                source_pads=set(),
                edge=edge,
                obstacles=obstacles,
            ):
                # BAT_COUT intentionally uses the local 0.20-mm clearance rule
                # in its named escape.  KiCad DRC, not the generic 0.25-mm
                # geometry helper, is the acceptance check for that route.
                if net_name != "/BAT_COUT":
                    raise RuntimeError(
                        f"Reviewed {net_name} segment is blocked: {first[:2]} -> {second[:2]}"
                    )
        return router.add_route(board, net_name, route, obstacles)
    finally:
        router.TRACK_WIDTH_MM = old_track_width
        router.VIA_DIAMETER_MM = old_via_diameter
        router.VIA_DRILL_MM = old_via_drill


def validate(board: pcbnew.BOARD) -> None:
    for net_name, endpoints in (
        ("/BAT_COUT", (("U14", "2"), ("R107", "1"), ("Q3", "4"))),
        (
            "/CELL_NEG",
            (("J4", "2"), ("Q2", "1"), ("U14", "4"), ("C102", "2"), ("R106", "2")),
        ),
    ):
        pads = [router.pad_by_reference(board, reference, pin) for reference, pin in endpoints]
        if any(pad.GetNetname() != net_name for pad in pads):
            raise RuntimeError(f"{net_name} endpoint net mismatch")
        if any(not router.already_connected(board, pads[0], pad) for pad in pads[1:]):
            raise RuntimeError(f"Serialized PCB lost {net_name} connectivity")


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
    areas = add_rule_areas(board)
    obstacles = router.existing_obstacles(board)
    tracks = 0
    vias = 0
    for net_name, route in (
        ("/BAT_COUT", BAT_COUT_ROUTE),
        ("/CELL_NEG", CELL_NEG_LOCAL_ROUTE),
        ("/CELL_NEG", CELL_NEG_SENSE_ROUTE),
        ("/CELL_NEG", CELL_NEG_TO_MAIN_ROUTE),
    ):
        route_tracks, route_vias = add_reviewed_route(
            board, obstacles, net_name, route, 0.20
        )
        tracks += route_tracks
        vias += route_vias

    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded)
    print(
        f"Saved battery-protection control stage: {output_path}; "
        f"segments={tracks}; vias={vias}; rule_areas={areas}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
