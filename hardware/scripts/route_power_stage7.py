"""Add the two narrow L3 5-V distribution corridors and their fanouts.

The uninterrupted return plane remains GND on L2.  L3 is primarily +3V3,
but two higher-priority, narrow copper corridors carry +5V_RAW and +5V_AUX.
This avoids long fine-width outer-layer power routes through the densely
packed lower half of the card while retaining one solid return plane.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew

import route_plane_fanouts as fanout


RAW = "/+5V_RAW"
AUX = "/+5V_AUX"
RAW_ZONE = "L3_5V_RAW_DISTRIBUTION"
AUX_ZONE = "L3_5V_AUX_DISTRIBUTION"
U17_AREA = "U17_RAW5V_FINE_ESCAPE"
LED1_AREA = "LED1_RAW5V_FINE_ESCAPE"
J5_AUX_AREA = "J5_AUX_HEADER_ESCAPE"


def line_rect(
    start: tuple[float, float], end: tuple[float, float], width_mm: float
) -> tuple[float, float, float, float]:
    x1, y1 = start
    x2, y2 = end
    half = width_mm / 2.0
    if abs(y1 - y2) < 0.001:
        return min(x1, x2) - half, y1 - half, max(x1, x2) + half, y1 + half
    if abs(x1 - x2) < 0.001:
        return x1 - half, min(y1, y2) - half, x1 + half, max(y1, y2) + half
    raise RuntimeError("L3 corridor segments must be orthogonal")


def union_boundary(
    rectangles: tuple[tuple[float, float, float, float], ...]
) -> tuple[tuple[float, float], ...]:
    """Return one clockwise outline for a connected union of rectangles."""
    xs = sorted({value for rectangle in rectangles for value in (rectangle[0], rectangle[2])})
    ys = sorted({value for rectangle in rectangles for value in (rectangle[1], rectangle[3])})
    filled: set[tuple[int, int]] = set()
    for x_index in range(len(xs) - 1):
        for y_index in range(len(ys) - 1):
            center_x = (xs[x_index] + xs[x_index + 1]) / 2.0
            center_y = (ys[y_index] + ys[y_index + 1]) / 2.0
            if any(
                left < center_x < right and top < center_y < bottom
                for left, top, right, bottom in rectangles
            ):
                filled.add((x_index, y_index))

    edges: dict[tuple[float, float], tuple[float, float]] = {}
    for x_index, y_index in filled:
        if (x_index, y_index - 1) not in filled:
            edges[(xs[x_index], ys[y_index])] = (xs[x_index + 1], ys[y_index])
        if (x_index + 1, y_index) not in filled:
            edges[(xs[x_index + 1], ys[y_index])] = (
                xs[x_index + 1],
                ys[y_index + 1],
            )
        if (x_index, y_index + 1) not in filled:
            edges[(xs[x_index + 1], ys[y_index + 1])] = (
                xs[x_index],
                ys[y_index + 1],
            )
        if (x_index - 1, y_index) not in filled:
            edges[(xs[x_index], ys[y_index + 1])] = (xs[x_index], ys[y_index])

    start = min(edges, key=lambda position: (position[1], position[0]))
    result = [start]
    current = start
    while True:
        current = edges[current]
        if current == start:
            break
        result.append(current)
    return tuple(result)


def add_distribution_zone(
    board: pcbnew.BOARD,
    name: str,
    net_name: str,
    lines: tuple[tuple[tuple[float, float], tuple[float, float], float], ...],
    priority: int,
) -> None:
    if any(zone.GetZoneName() == name for zone in board.Zones()):
        raise RuntimeError(f"Input already contains {name}")
    zone = pcbnew.ZONE(board)
    zone.SetZoneName(name)
    zone.SetLayer(pcbnew.In2_Cu)
    zone.SetNet(board.FindNet(net_name))
    zone.SetLocalClearance(pcbnew.FromMM(0.25))
    zone.SetMinThickness(pcbnew.FromMM(0.20))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(pcbnew.FromMM(0.25))
    zone.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.30))
    zone.SetMinIslandArea(0)
    zone.SetAssignedPriority(priority)
    outline = zone.Outline()
    outline.NewOutline()
    rectangles = tuple(line_rect(start, end, width) for start, end, width in lines)
    for x_mm, y_mm in union_boundary(rectangles):
        outline.Append(pcbnew.VECTOR2I_MM(x_mm, y_mm))
    board.Add(zone)


def add_rule_area(
    board: pcbnew.BOARD,
    name: str,
    corners: tuple[tuple[float, float], ...],
    layer: int = pcbnew.F_Cu,
) -> None:
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
    for x_mm, y_mm in corners:
        outline.Append(pcbnew.VECTOR2I_MM(x_mm, y_mm))
    board.Add(area)


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
    layer: int,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(*start))
    track.SetEnd(pcbnew.VECTOR2I_MM(*end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def add_via(
    board: pcbnew.BOARD,
    net_name: str,
    position: tuple[float, float],
    diameter_mm: float = 0.50,
    drill_mm: float = 0.30,
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I_MM(*position))
    via.SetWidth(pcbnew.FromMM(diameter_mm))
    via.SetDrill(pcbnew.FromMM(drill_mm))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(board.FindNet(net_name))
    via.SetLocked(True)
    via.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
    via.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    board.Add(via)


def point_of(item: pcbnew.BOARD_CONNECTED_ITEM, start: bool) -> tuple[float, float]:
    position = item.GetStart() if start else item.GetEnd()
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def remove_u17_blocking_ground(board: pcbnew.BOARD) -> int:
    pairs = (
        ((38.6625, 54.5000), (38.9125, 54.2500)),
        ((38.6625, 55.2500), (38.6625, 54.5000)),
        ((38.9125, 54.2500), (40.9125, 54.2500)),
        ((38.9125, 55.5000), (38.6625, 55.2500)),
        ((39.6625, 55.5000), (38.9125, 55.5000)),
    )
    removal: list[pcbnew.PCB_TRACK] = []
    for item in board.Tracks():
        if (
            isinstance(item, pcbnew.PCB_VIA)
            or item.GetNetname() != "/GND"
            or item.GetLayer() != pcbnew.F_Cu
        ):
            continue
        start = point_of(item, True)
        end = point_of(item, False)
        if any(
            (math.dist(start, first) < 0.002 and math.dist(end, second) < 0.002)
            or (math.dist(start, second) < 0.002 and math.dist(end, first) < 0.002)
            for first, second in pairs
        ):
            removal.append(item)
    if len(removal) != len(pairs):
        raise RuntimeError(f"Expected five U17-blocking GND segments, found {len(removal)}")
    for item in removal:
        board.Remove(item)
    return len(removal)


RAW_LINES = (
    # R610 must pass two dense rows of existing plane vias.  A reviewed
    # 0.80-mm dogleg avoids them instead of letting a broad pour be split.
    ((68.313, 25.962), (68.313, 36.962), 0.80),
    ((68.313, 36.962), (68.813, 36.962), 0.80),
    ((68.813, 36.962), (68.813, 38.712), 0.80),
    ((68.813, 38.712), (88.313, 38.712), 0.80),
    ((88.313, 38.712), (88.313, 39.462), 0.80),
    ((88.313, 39.462), (91.290, 39.462), 0.80),
    ((91.290, 39.462), (91.290, 39.825), 0.80),
    ((96.9173, 30.346), (96.9173, 39.825), 0.80),
    ((91.290, 39.825), (96.9173, 39.825), 0.80),
    ((91.290, 39.825), (91.290, 62.000), 1.00),
    ((77.890, 39.825), (91.290, 39.825), 1.00),
    ((77.890, 39.825), (77.890, 62.000), 1.00),
    ((63.800, 62.000), (92.600, 62.000), 1.00),
    ((50.515, 59.800), (75.000, 59.800), 1.00),
    ((64.300, 59.800), (64.300, 71.200), 1.00),
    ((34.540, 71.200), (64.825, 71.200), 1.00),
    ((34.540, 59.800), (34.540, 71.200), 1.00),
    ((34.540, 59.800), (50.515, 59.800), 1.00),
    ((39.0625, 54.050), (39.0625, 59.800), 1.00),
    ((64.300, 65.900), (67.545, 65.900), 1.00),
    # Three leaf vias need explicit detours around nearby through-vias.
    ((70.2153, 60.7716), (70.2153, 61.0216), 0.80),
    ((70.2153, 61.0216), (72.2153, 61.0216), 0.80),
    ((72.2153, 60.2716), (72.2153, 61.0216), 0.80),
    ((72.2153, 60.2716), (75.0000, 60.2716), 0.80),
    ((75.0000, 59.9925), (75.0000, 60.2716), 0.80),
    ((87.7900, 31.8250), (86.2900, 31.8250), 0.80),
    ((86.2900, 31.8250), (86.2900, 38.3250), 0.80),
    ((86.2900, 38.3250), (88.3130, 38.3250), 0.80),
    ((88.3130, 38.3250), (88.3130, 38.7120), 0.80),
    ((39.0625, 54.0500), (39.0625, 57.3000), 0.80),
    ((39.0625, 57.3000), (42.8125, 57.3000), 0.80),
    ((42.8125, 57.3000), (42.8125, 57.8000), 0.80),
    ((42.8125, 57.8000), (43.5625, 57.8000), 0.80),
    ((43.5625, 57.8000), (43.5625, 59.5500), 0.80),
    ((43.5625, 59.5500), (50.5150, 59.5500), 0.80),
    ((50.5150, 59.5500), (50.5150, 59.7500), 0.80),
)

AUX_LINES = (
    # U15/C119 to TP110: snake to the left of the two USB-C shield stakes.
    ((94.6087, 61.1624), (94.6087, 53.4124), 0.80),
    ((94.6087, 53.4124), (97.3587, 53.4124), 0.80),
    ((97.3587, 53.4124), (97.3587, 52.9124), 0.80),
    ((97.3587, 52.9124), (98.1087, 52.9124), 0.80),
    ((98.1087, 52.9124), (98.1087, 48.6624), 0.80),
    ((96.3587, 48.6624), (98.1087, 48.6624), 0.80),
    ((96.3587, 44.9124), (96.3587, 48.6624), 0.80),
    ((96.3587, 44.9124), (98.1087, 44.9124), 0.80),
    ((98.1087, 31.1624), (98.1087, 44.9124), 0.80),
    ((98.1087, 31.1624), (99.4648, 31.1624), 0.80),
    ((99.4648, 30.9884), (99.4648, 31.1624), 0.80),
    # Local branches from the remaining AUX fanout vias.
    ((97.1039, 63.3400), (95.6039, 63.3400), 0.80),
    ((95.6039, 63.0900), (95.6039, 63.3400), 0.80),
    ((94.8539, 63.0900), (95.6039, 63.0900), 0.80),
    ((94.8539, 61.5900), (94.8539, 63.0900), 0.80),
    ((94.6087, 61.5900), (94.8539, 61.5900), 0.80),
    ((94.6087, 61.1624), (94.6087, 61.5900), 0.80),
    ((100.0000, 67.5550), (97.2500, 67.5550), 0.80),
    ((97.2500, 63.8050), (97.2500, 67.5550), 0.80),
    ((97.1039, 63.8050), (97.2500, 63.8050), 0.80),
    ((97.1039, 63.3400), (97.1039, 63.8050), 0.80),
    # Header bridge via to C118, above the Sub-GHz spring cut-out.
    ((72.9000, 64.7500), (82.8000, 64.7500), 0.80),
    ((82.8000, 63.5000), (82.8000, 64.7500), 0.80),
    ((82.8000, 63.5000), (85.2000, 63.5000), 0.80),
    ((85.2000, 63.5000), (85.2000, 65.5500), 0.80),
    ((85.2000, 65.5500), (88.0000, 65.5500), 0.80),
    ((88.0000, 65.5500), (88.0000, 66.0500), 0.80),
    ((88.0000, 66.0500), (89.5000, 66.0500), 0.80),
    ((89.5000, 66.0500), (89.5000, 67.3000), 0.80),
    ((89.5000, 67.3000), (100.0000, 67.3000), 0.80),
    ((100.0000, 67.3000), (100.0000, 67.5550), 0.80),
)


def route(board: pcbnew.BOARD) -> tuple[int, int, int, list[str]]:
    add_distribution_zone(board, RAW_ZONE, RAW, RAW_LINES, 3)
    add_distribution_zone(board, AUX_ZONE, AUX, AUX_LINES, 4)
    add_rule_area(
        board,
        U17_AREA,
        ((38.70, 53.70), (40.00, 53.70), (40.00, 55.10), (38.70, 55.10)),
    )
    add_rule_area(
        board,
        LED1_AREA,
        ((49.45, 59.30), (50.85, 59.30), (50.85, 60.15), (49.45, 60.15)),
    )
    add_rule_area(
        board,
        J5_AUX_AREA,
        ((59.20, 64.80), (69.50, 64.80), (69.50, 72.50), (59.20, 72.50)),
        pcbnew.B_Cu,
    )

    add_track(board, RAW, (90.195, 39.825), (91.290, 39.825), 0.50, pcbnew.B_Cu)
    add_via(board, RAW, (91.290, 39.825))

    remove_u17_blocking_ground(board)
    add_track(board, RAW, (39.6625, 54.850), (39.0625, 54.050), 0.15, pcbnew.F_Cu)
    add_via(board, RAW, (39.0625, 54.050), 0.45, 0.20)

    add_track(board, RAW, (49.915, 59.750), (50.515, 59.750), 0.15, pcbnew.F_Cu)
    add_via(board, RAW, (50.515, 59.750))
    add_track(board, RAW, (57.915, 59.750), (58.165, 59.750), 0.50, pcbnew.F_Cu)
    add_via(board, RAW, (58.165, 59.750))

    # Escape J5.29 through the centre of the 2.54-mm header grid.  The route
    # crosses the RAW L3 corridor on B.Cu, then changes to AUX on L3 only after
    # it is east of RAW, so the two inner-plane rails never intersect.
    j5_aux_path = (
        (59.8100, 72.0800),
        (61.0800, 70.8100),
        (61.0800, 63.1900),
        (63.7000, 63.1900),
        (63.7000, 62.5000),
        (68.3000, 62.5000),
        (68.3000, 64.7500),
        (72.9000, 64.7500),
    )
    for start, end in zip(j5_aux_path, j5_aux_path[1:]):
        add_track(board, AUX, start, end, 0.20, pcbnew.B_Cu)
    add_via(board, AUX, (72.9000, 64.7500), 0.45, 0.20)

    # C603 is isolated on the far side of the AUX corridor.  Keep it on B.Cu
    # and join it to TP109; one plane via at TP109 then feeds the RAW corridor.
    c603_path = (
        (102.6950, 29.8250),
        (102.2973, 30.5960),
        (102.2973, 30.8460),
        (100.5473, 32.5960),
        (100.2973, 32.5960),
        (100.0473, 32.8460),
        (99.7973, 32.5960),
        (99.5473, 32.5960),
        (98.5473, 31.5960),
        (97.5473, 31.5960),
        (96.2973, 30.3460),
        (96.0473, 30.3460),
    )
    for start, end in zip(c603_path, c603_path[1:]):
        add_track(board, RAW, start, end, 0.50, pcbnew.B_Cu)
    add_track(board, RAW, (96.0473, 30.3460), (96.9173, 30.3460), 0.50, pcbnew.B_Cu)
    add_via(board, RAW, (96.9173, 30.3460))

    previous_targets = fanout.TARGET_NETS
    previous_planes = fanout.PLANE_LAYER
    previous_manual = fanout.MANUAL_FANOUT_PADS
    previous_diameter = fanout.VIA_DIAMETER_MM
    previous_drill = fanout.VIA_DRILL_MM
    previous_clearance = fanout.DIFFERENT_NET_CLEARANCE_MM
    previous_radius = fanout.GRID_MAX_RADIUS_MM
    previous_distance = fanout.EXISTING_VIA_MAX_DISTANCE_MM
    try:
        fanout.TARGET_NETS = {RAW: 0.50, AUX: 0.20}
        fanout.PLANE_LAYER = {RAW: pcbnew.In2_Cu, AUX: pcbnew.In2_Cu}
        fanout.MANUAL_FANOUT_PADS = frozenset(
            {("U17", "1"), ("LED1", "1"), ("LED3", "1"), ("C603", "1"), ("TP109", "1")}
        )
        fanout.VIA_DIAMETER_MM = 0.50
        fanout.VIA_DRILL_MM = 0.30
        fanout.DIFFERENT_NET_CLEARANCE_MM = 0.20
        fanout.GRID_MAX_RADIUS_MM = 8.0
        fanout.EXISTING_VIA_MAX_DISTANCE_MM = 10.0
        return fanout.route(board)
    finally:
        fanout.TARGET_NETS = previous_targets
        fanout.PLANE_LAYER = previous_planes
        fanout.MANUAL_FANOUT_PADS = previous_manual
        fanout.VIA_DIAMETER_MM = previous_diameter
        fanout.VIA_DRILL_MM = previous_drill
        fanout.DIFFERENT_NET_CLEARANCE_MM = previous_clearance
        fanout.GRID_MAX_RADIUS_MM = previous_radius
        fanout.EXISTING_VIA_MAX_DISTANCE_MM = previous_distance


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
    added, shared, grid, skipped = route(board)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    print(
        f"Saved split-5V PCB: {output_path}; fanouts={added}; "
        f"shared={shared}; grid={grid}; skipped={len(skipped)}"
    )
    for entry in skipped:
        print(f"SKIPPED {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
