"""Route the seven non-resonant HTRC110 control nets on the outer layers.

The resonant/RX/clock analogue island is owned by ``route_lf_rfid.py`` and is
never touched here.  This pass connects the ESP32, level translators, internal
control expander and HTRC110 with 0.20-mm digital routes.  A small two-layer
maze router respects existing copper, component/antenna keepouts and the board
edge; ordinary 0.60/0.30-mm through vias are used only where a side transition
is required.
"""

from __future__ import annotations

import argparse
import heapq
import math
from dataclasses import dataclass
from pathlib import Path

import pcbnew

from route_plane_fanouts import (
    B,
    DIFFERENT_NET_CLEARANCE_MM,
    EDGE_CLEARANCE_MM,
    F,
    Rect,
    SUBGHZ_NOTCH,
    CopperObstacle,
    board_rect,
    compact_path,
    distance,
    existing_obstacles,
    item_key,
    mm,
    nearby_obstacles,
    pad_layer,
    point,
    point_segment_distance,
    rect_of,
    segment_intersects_rect,
    simplify_grid_path,
    track_segment_is_clear,
    xy,
)


TRACK_WIDTH_MM = 0.20
VIA_DIAMETER_MM = 0.60
VIA_DRILL_MM = 0.30
GRID_MM = 0.25
ROUTE_PRIORITY = {
    "/SPI_MOSI": 0,
    "/SPI_SCK": 1,
    "/SPI_MISO": 2,
    "/LF_SCLK_5V": 0,
    "/LF_DIN_5V": 2,
    "/LF_DOUT_5V": 4,
    "/LF_RFID_EN": 6,
}

CONNECTIONS = (
    ("/LF_RFID_EN", "U18", "9", "U17", "3"),
    ("/LF_DIN_5V", "U21", "3", "U4", "9"),
    ("/LF_SCLK_5V", "U21", "6", "U4", "8"),
    ("/LF_DOUT_5V", "U4", "10", "U22", "2"),
    ("/SPI_MOSI", "U21", "2", "R402", "1"),
    ("/SPI_SCK", "U21", "5", "R401", "1"),
    ("/SPI_MISO", "U22", "4", "R403", "1"),
)

LF_FINE_PITCH_REFS = frozenset({"U1", "U4", "U17", "U18", "U21", "U22"})


def signal_clearance(net_name: str) -> float:
    if net_name in {"/SPI_SCK", "/SPI_MOSI", "/SPI_MISO"}:
        return 0.15
    return 0.15


def same_family_clearance(net_name: str, obstacle_net: str) -> float | None:
    spi = {"/SPI_SCK", "/SPI_MOSI", "/SPI_MISO"}
    if net_name in spi and obstacle_net in spi:
        return 0.12
    if net_name.startswith("/LF_") and obstacle_net.startswith("/LF_"):
        return 0.12
    return None


def routing_obstacles(net_name: str, obstacles: list[CopperObstacle]) -> list[CopperObstacle]:
    """Ignore lower-priority, not-yet-committed sibling routes.

    Routes are still checked against all unrelated copper.  Sibling SPI/LF
    paths are generated independently and the deterministic priority ordering
    keeps the selected result reproducible; the final KiCad DRC remains the
    acceptance check for spacing between those paths.
    """
    priority = ROUTE_PRIORITY[net_name]
    return [
        obstacle
        for obstacle in obstacles
        if obstacle.kind not in {"track", "via"}
        or obstacle.net not in ROUTE_PRIORITY
        or ROUTE_PRIORITY[obstacle.net] >= priority
    ]


def obstacle_rect(obstacle: CopperObstacle) -> Rect:
    if obstacle.kind == "pad":
        result = obstacle.geometry
    elif obstacle.kind == "via":
        center, radius = obstacle.geometry
        result = Rect(center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    elif obstacle.kind == "track":
        start, end, radius, _ = obstacle.geometry
        result = Rect(
            min(start[0], end[0]) - radius,
            min(start[1], end[1]) - radius,
            max(start[0], end[0]) + radius,
            max(start[1], end[1]) + radius,
        )
    elif obstacle.kind in {"copper_graphic", "keepout"}:
        result = obstacle.geometry[0]
    else:
        raise RuntimeError(f"Unknown obstacle type: {obstacle.kind}")
    assert isinstance(result, Rect)
    return result


@dataclass
class SpatialIndex:
    obstacles: list[CopperObstacle]
    cell_mm: float = 2.0

    def __post_init__(self) -> None:
        self.cells: dict[tuple[int, int], list[int]] = {}
        for index, obstacle in enumerate(self.obstacles):
            box = obstacle_rect(obstacle).expanded(0.8)
            x_start = math.floor(box.left / self.cell_mm)
            x_end = math.floor(box.right / self.cell_mm)
            y_start = math.floor(box.top / self.cell_mm)
            y_end = math.floor(box.bottom / self.cell_mm)
            for x_index in range(x_start, x_end + 1):
                for y_index in range(y_start, y_end + 1):
                    self.cells.setdefault((x_index, y_index), []).append(index)

    def query_rect(self, box: Rect) -> list[CopperObstacle]:
        indices: set[int] = set()
        x_start = math.floor(box.left / self.cell_mm)
        x_end = math.floor(box.right / self.cell_mm)
        y_start = math.floor(box.top / self.cell_mm)
        y_end = math.floor(box.bottom / self.cell_mm)
        for x_index in range(x_start, x_end + 1):
            for y_index in range(y_start, y_end + 1):
                indices.update(self.cells.get((x_index, y_index), ()))
        return [self.obstacles[index] for index in indices]

    def query_segment(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> list[CopperObstacle]:
        return self.query_rect(
            Rect(
                min(start[0], end[0]) - 0.8,
                min(start[1], end[1]) - 0.8,
                max(start[0], end[0]) + 0.8,
                max(start[1], end[1]) + 0.8,
            )
        )

    def query_point(self, position: tuple[float, float]) -> list[CopperObstacle]:
        return self.query_rect(
            Rect(position[0] - 0.8, position[1] - 0.8, position[0] + 0.8, position[1] + 0.8)
        )


def pad_by_reference(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"LF routing footprint is missing: {reference}")
    pads = [pad for pad in footprint.Pads() if pad.GetNumber() == number]
    if len(pads) != 1:
        raise RuntimeError(f"Expected one {reference}.{number} pad, got {len(pads)}")
    return pads[0]


def already_connected(board: pcbnew.BOARD, start: pcbnew.PAD, end: pcbnew.PAD) -> bool:
    board.BuildConnectivity()
    return any(item_key(item) == item_key(end) for item in board.GetConnectivity().GetConnectedItems(start))


def signal_via_is_clear(
    *,
    net_name: str,
    position: tuple[float, float],
    endpoint_pad_ids: set[str],
    edge: Rect,
    obstacles: list[CopperObstacle],
) -> bool:
    radius = VIA_DIAMETER_MM / 2.0
    if not edge.expanded(-(EDGE_CLEARANCE_MM + radius + 0.05)).contains(position):
        return False
    if SUBGHZ_NOTCH.expanded(EDGE_CLEARANCE_MM + radius).contains(position):
        return False
    for obstacle in obstacles:
        if obstacle.net == net_name:
            continue
        sibling_clearance = same_family_clearance(net_name, obstacle.net)
        if obstacle.kind == "pad":
            pad = obstacle.owner
            assert isinstance(pad, pcbnew.PAD)
            pad_rect = obstacle.geometry
            assert isinstance(pad_rect, Rect)
            if item_key(pad) in endpoint_pad_ids:
                if pad_rect.expanded(radius + 0.08).contains(position):
                    return False
            elif pad_rect.expanded(radius + signal_clearance(net_name)).contains(position):
                return False
        elif obstacle.kind == "via":
            center, other_radius = obstacle.geometry
            via_clearance = sibling_clearance if sibling_clearance is not None else signal_clearance(net_name)
            if distance(position, center) < radius + other_radius + via_clearance:
                return False
        elif obstacle.kind == "track":
            other_start, other_end, other_radius, _ = obstacle.geometry
            track_clearance = sibling_clearance if sibling_clearance is not None else signal_clearance(net_name)
            if point_segment_distance(position, other_start, other_end) < (
                radius + other_radius + track_clearance
            ):
                return False
        elif obstacle.kind == "copper_graphic":
            graphic_rect, _ = obstacle.geometry
            if graphic_rect.expanded(radius + signal_clearance(net_name)).contains(position):
                return False
        elif obstacle.kind == "keepout":
            keepout_rect, _, _, disallow_vias, _ = obstacle.geometry
            if disallow_vias and keepout_rect.expanded(radius).contains(position):
                return False
    return True


def local_route_obstacles(
    obstacles: list[CopperObstacle],
    start: tuple[float, float],
    end: tuple[float, float],
    expansion: float,
) -> list[CopperObstacle]:
    route_rect = Rect(
        min(start[0], end[0]) - expansion,
        min(start[1], end[1]) - expansion,
        max(start[0], end[0]) + expansion,
        max(start[1], end[1]) + expansion,
    )
    center = ((route_rect.left + route_rect.right) / 2.0, (route_rect.top + route_rect.bottom) / 2.0)
    radius = math.hypot(route_rect.right - route_rect.left, route_rect.bottom - route_rect.top) / 2.0
    return nearby_obstacles(obstacles, center, radius + 1.0)


def find_escape_paths(
    *,
    net_name: str,
    pad: pcbnew.PAD,
    endpoint_pad_ids: set[str],
    edge: Rect,
    obstacles: list[CopperObstacle],
    maximum_paths: int = 14,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    layer = pad_layer(pad)
    if layer is None:
        return ()
    start = xy(pad.GetPosition())
    local_obstacles = nearby_obstacles(obstacles, start, 6.0)
    spatial = SpatialIndex(local_obstacles)
    step = 0.20
    queue: list[tuple[float, int, int]] = [(0.0, 0, 0)]
    cost: dict[tuple[int, int], float] = {(0, 0): 0.0}
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    results: list[tuple[tuple[float, float], ...]] = []
    result_positions: list[tuple[float, float]] = []
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    while queue and len(cost) < 80_000:
        current_cost, ix, iy = heapq.heappop(queue)
        key = (ix, iy)
        if current_cost > cost.get(key, math.inf) + 1e-9:
            continue
        current = (start[0] + ix * step, start[1] + iy * step)
        if current_cost >= 0.60 and signal_via_is_clear(
            net_name=net_name,
            position=current,
            endpoint_pad_ids=endpoint_pad_ids,
            edge=edge,
            obstacles=spatial.query_point(current),
        ):
            # Do not stop at the nearest legal via.  Dense component areas can
            # put that candidate in a copper pocket which has no usable long
            # route on the opposite layer.  Keep several candidates in
            # different directions so the middle-router can select an open
            # corridor.
            if all(distance(current, position) >= 0.90 for position in result_positions):
                keys = [key]
                while keys[-1] != (0, 0):
                    keys.append(previous[keys[-1]])
                keys.reverse()
                points = [(start[0] + x * step, start[1] + y * step) for x, y in keys]
                results.append(simplify_grid_path(points))
                result_positions.append(current)
                if len(results) >= maximum_paths:
                    return tuple(results)
        for dx_index, dy_index in directions:
            next_key = (ix + dx_index, iy + dy_index)
            next_position = (
                start[0] + next_key[0] * step,
                start[1] + next_key[1] * step,
            )
            if distance(start, next_position) > 5.0:
                continue
            if not track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=current,
                end=next_position,
                width_mm=TRACK_WIDTH_MM,
                source_pads=endpoint_pad_ids,
                edge=edge,
                obstacles=spatial.query_segment(current, next_position),
            ):
                continue
            step_cost = step * (math.sqrt(2.0) if dx_index and dy_index else 1.0)
            candidate_cost = current_cost + step_cost
            if candidate_cost + 1e-9 >= cost.get(next_key, math.inf):
                continue
            cost[next_key] = candidate_cost
            previous[next_key] = key
            heapq.heappush(queue, (candidate_cost, *next_key))
    return tuple(results)


def find_fixed_layer_path(
    *,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: int,
    endpoint_pad_ids: set[str],
    edge: Rect,
    obstacles: list[CopperObstacle],
    expansion: float = 8.0,
) -> tuple[tuple[float, float], ...] | None:
    local_obstacles = local_route_obstacles(obstacles, start, end, expansion)
    spatial = SpatialIndex(local_obstacles)
    left = min(start[0], end[0]) - expansion
    right = max(start[0], end[0]) + expansion
    top = min(start[1], end[1]) - expansion
    bottom = max(start[1], end[1]) + expansion
    start_state = (0, 0)
    queue: list[tuple[float, float, tuple[int, int]]] = [
        (distance(start, end), 0.0, start_state)
    ]
    cost: dict[tuple[int, int], float] = {start_state: 0.0}
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    while queue and len(cost) < 140_000:
        _, current_cost, state = heapq.heappop(queue)
        if current_cost > cost.get(state, math.inf) + 1e-9:
            continue
        current = (start[0] + state[0] * GRID_MM, start[1] + state[1] * GRID_MM)
        if distance(current, end) <= 0.65 and track_segment_is_clear(
            net_name=net_name,
            layer=layer,
            start=current,
            end=end,
            width_mm=TRACK_WIDTH_MM,
            source_pads=endpoint_pad_ids,
            edge=edge,
            obstacles=spatial.query_segment(current, end),
        ):
            states = [state]
            while states[-1] != start_state:
                states.append(previous[states[-1]])
            states.reverse()
            points = [(start[0] + x * GRID_MM, start[1] + y * GRID_MM) for x, y in states]
            points.append(end)
            return simplify_grid_path(points)
        for dx_index, dy_index in directions:
            next_state = (state[0] + dx_index, state[1] + dy_index)
            next_position = (
                start[0] + next_state[0] * GRID_MM,
                start[1] + next_state[1] * GRID_MM,
            )
            if not (left <= next_position[0] <= right and top <= next_position[1] <= bottom):
                continue
            if not track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=current,
                end=next_position,
                width_mm=TRACK_WIDTH_MM,
                source_pads=endpoint_pad_ids,
                edge=edge,
                obstacles=spatial.query_segment(current, next_position),
            ):
                continue
            step_cost = GRID_MM * (math.sqrt(2.0) if dx_index and dy_index else 1.0)
            candidate_cost = current_cost + step_cost
            if candidate_cost + 1e-9 >= cost.get(next_state, math.inf):
                continue
            cost[next_state] = candidate_cost
            previous[next_state] = state
            heapq.heappush(
                queue,
                (candidate_cost + distance(next_position, end), candidate_cost, next_state),
            )
    return None


def find_fixed_layer_path_to_goals(
    *,
    net_name: str,
    start: tuple[float, float],
    ends: tuple[tuple[float, float], ...],
    layer: int,
    endpoint_pad_ids: set[str],
    edge: Rect,
    obstacles: list[CopperObstacle],
    expansion: float = 8.0,
) -> tuple[tuple[tuple[float, float], ...], int] | None:
    """Route from one escape to any compatible escape in one A* pass."""
    if not ends:
        return None
    route_left = min((start[0], *(position[0] for position in ends)))
    route_right = max((start[0], *(position[0] for position in ends)))
    route_top = min((start[1], *(position[1] for position in ends)))
    route_bottom = max((start[1], *(position[1] for position in ends)))
    route_center = ((route_left + route_right) / 2.0, (route_top + route_bottom) / 2.0)
    route_radius = math.hypot(route_right - route_left, route_bottom - route_top) / 2.0
    local_obstacles = nearby_obstacles(obstacles, route_center, route_radius + expansion + 1.0)
    spatial = SpatialIndex(local_obstacles)
    left = route_left - expansion
    right = route_right + expansion
    top = route_top - expansion
    bottom = route_bottom + expansion
    start_state = (0, 0)
    queue: list[tuple[float, float, tuple[int, int]]] = [
        (min(distance(start, end) for end in ends), 0.0, start_state)
    ]
    cost: dict[tuple[int, int], float] = {start_state: 0.0}
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    while queue and len(cost) < 140_000:
        _, current_cost, state = heapq.heappop(queue)
        if current_cost > cost.get(state, math.inf) + 1e-9:
            continue
        current = (start[0] + state[0] * GRID_MM, start[1] + state[1] * GRID_MM)
        ordered_goals = sorted(enumerate(ends), key=lambda entry: distance(current, entry[1]))
        for goal_index, end in ordered_goals:
            if distance(current, end) > 0.65:
                break
            if not track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=current,
                end=end,
                width_mm=TRACK_WIDTH_MM,
                source_pads=endpoint_pad_ids,
                edge=edge,
                obstacles=spatial.query_segment(current, end),
            ):
                continue
            states = [state]
            while states[-1] != start_state:
                states.append(previous[states[-1]])
            states.reverse()
            points = [(start[0] + x * GRID_MM, start[1] + y * GRID_MM) for x, y in states]
            points.append(end)
            return simplify_grid_path(points), goal_index
        for dx_index, dy_index in directions:
            next_state = (state[0] + dx_index, state[1] + dy_index)
            next_position = (
                start[0] + next_state[0] * GRID_MM,
                start[1] + next_state[1] * GRID_MM,
            )
            if not (left <= next_position[0] <= right and top <= next_position[1] <= bottom):
                continue
            if not track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=current,
                end=next_position,
                width_mm=TRACK_WIDTH_MM,
                source_pads=endpoint_pad_ids,
                edge=edge,
                obstacles=spatial.query_segment(current, next_position),
            ):
                continue
            step_cost = GRID_MM * (math.sqrt(2.0) if dx_index and dy_index else 1.0)
            candidate_cost = current_cost + step_cost
            if candidate_cost + 1e-9 >= cost.get(next_state, math.inf):
                continue
            cost[next_state] = candidate_cost
            previous[next_state] = state
            estimate = candidate_cost + min(distance(next_position, end) for end in ends)
            heapq.heappush(queue, (estimate, candidate_cost, next_state))
    return None


def decomposed_route(
    *,
    net_name: str,
    start_pad: pcbnew.PAD,
    end_pad: pcbnew.PAD,
    edge: Rect,
    obstacles: list[CopperObstacle],
) -> tuple[tuple[float, float, int], ...] | None:
    start_layer = pad_layer(start_pad)
    end_layer = pad_layer(end_pad)
    if start_layer is None or end_layer is None:
        return None
    start = xy(start_pad.GetPosition())
    end = xy(end_pad.GetPosition())
    endpoint_ids = {item_key(start_pad), item_key(end_pad)}
    if start_layer == end_layer:
        direct = find_fixed_layer_path(
            net_name=net_name,
            start=start,
            end=end,
            layer=start_layer,
            endpoint_pad_ids=endpoint_ids,
            edge=edge,
            obstacles=obstacles,
        )
        if direct is not None:
            return tuple((position[0], position[1], start_layer) for position in direct)
        start_escapes = find_escape_paths(
            net_name=net_name,
            pad=start_pad,
            endpoint_pad_ids=endpoint_ids,
            edge=edge,
            obstacles=obstacles,
        )
        end_escapes = find_escape_paths(
            net_name=net_name,
            pad=end_pad,
            endpoint_pad_ids=endpoint_ids,
            edge=edge,
            obstacles=obstacles,
        )
        if not start_escapes or not end_escapes:
            return None
        other_layer = B if start_layer == F else F
        ordered_start_escapes = sorted(
            start_escapes,
            key=lambda path: len(path) + min(distance(path[-1], end[-1]) for end in end_escapes),
        )
        end_positions = tuple(path[-1] for path in end_escapes)
        for start_escape in ordered_start_escapes:
            middle_result = find_fixed_layer_path_to_goals(
                net_name=net_name,
                start=start_escape[-1],
                ends=end_positions,
                layer=other_layer,
                endpoint_pad_ids=endpoint_ids,
                edge=edge,
                obstacles=obstacles,
            )
            if middle_result is None:
                continue
            middle, end_index = middle_result
            end_escape = end_escapes[end_index]
            result = [(position[0], position[1], start_layer) for position in start_escape]
            result.append((start_escape[-1][0], start_escape[-1][1], other_layer))
            result.extend((position[0], position[1], other_layer) for position in middle[1:])
            result.append((end_escape[-1][0], end_escape[-1][1], end_layer))
            result.extend((position[0], position[1], end_layer) for position in reversed(end_escape[:-1]))
            return tuple(result)
        return None

    # Opposite-side endpoints need exactly one endpoint escape via.  Try both
    # orientations and keep the first legal fixed-layer middle route.
    for escape_pad, fixed_pad, escape_at_start in (
        (start_pad, end_pad, True),
        (end_pad, start_pad, False),
    ):
        escapes = find_escape_paths(
            net_name=net_name,
            pad=escape_pad,
            endpoint_pad_ids=endpoint_ids,
            edge=edge,
            obstacles=obstacles,
        )
        if not escapes:
            continue
        fixed_position = xy(fixed_pad.GetPosition())
        fixed_layer = pad_layer(fixed_pad)
        assert fixed_layer is not None
        for escape in escapes:
            if escape_at_start:
                middle_start, middle_end = escape[-1], fixed_position
            else:
                middle_start, middle_end = fixed_position, escape[-1]
            middle = find_fixed_layer_path(
                net_name=net_name,
                start=middle_start,
                end=middle_end,
                layer=fixed_layer,
                endpoint_pad_ids=endpoint_ids,
                edge=edge,
                obstacles=obstacles,
            )
            if middle is None:
                continue
            if escape_at_start:
                result = [(position[0], position[1], start_layer) for position in escape]
                result.append((escape[-1][0], escape[-1][1], fixed_layer))
                result.extend((position[0], position[1], fixed_layer) for position in middle[1:])
            else:
                result = [(position[0], position[1], start_layer) for position in middle]
                result.append((escape[-1][0], escape[-1][1], end_layer))
                result.extend((position[0], position[1], end_layer) for position in reversed(escape[:-1]))
            return tuple(result)
    return None


def find_route(
    *,
    net_name: str,
    start_pad: pcbnew.PAD,
    end_pad: pcbnew.PAD,
    edge: Rect,
    obstacles: list[CopperObstacle],
) -> tuple[tuple[float, float, int], ...] | None:
    split_route = decomposed_route(
        net_name=net_name,
        start_pad=start_pad,
        end_pad=end_pad,
        edge=edge,
        obstacles=obstacles,
    )
    if split_route is not None:
        return split_route
    start_layer = pad_layer(start_pad)
    end_layer = pad_layer(end_pad)
    if start_layer is None or end_layer is None:
        raise RuntimeError(f"LF endpoints must be one-sided SMD pads: {net_name}")
    start = xy(start_pad.GetPosition())
    end = xy(end_pad.GetPosition())
    endpoint_ids = {item_key(start_pad), item_key(end_pad)}
    # Dense analogue/RF placement can require a broad detour around the
    # central component fields.  Keep the search inside the board geometry,
    # but do not artificially confine it to the endpoint bounding box.
    expansion = 20.0
    local_obstacles = local_route_obstacles(obstacles, start, end, expansion)
    spatial = SpatialIndex(local_obstacles)
    left = min(start[0], end[0]) - expansion
    right = max(start[0], end[0]) + expansion
    top = min(start[1], end[1]) - expansion
    bottom = max(start[1], end[1]) + expansion

    # (grid x, grid y, layer); the grid is anchored at the exact start pad so
    # the first segment always begins at its electrical centre.
    start_state = (0, 0, start_layer)
    queue: list[tuple[float, float, tuple[int, int, int]]] = []
    heapq.heappush(queue, (distance(start, end), 0.0, start_state))
    cost: dict[tuple[int, int, int], float] = {start_state: 0.0}
    previous: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    goal_state: tuple[int, int, int] | None = None

    while queue and len(cost) < 600_000:
        _, current_cost, state = heapq.heappop(queue)
        if current_cost > cost.get(state, math.inf) + 1e-9:
            continue
        ix, iy, layer = state
        current = (start[0] + ix * GRID_MM, start[1] + iy * GRID_MM)
        if layer == end_layer and distance(current, end) <= 0.65 and track_segment_is_clear(
            net_name=net_name,
            layer=layer,
            start=current,
            end=end,
            width_mm=TRACK_WIDTH_MM,
            source_pads=endpoint_ids,
            edge=edge,
            obstacles=spatial.query_segment(current, end),
        ):
            goal_state = state
            break

        for dx_index, dy_index in directions:
            next_state = (ix + dx_index, iy + dy_index, layer)
            next_position = (
                start[0] + next_state[0] * GRID_MM,
                start[1] + next_state[1] * GRID_MM,
            )
            if not (left <= next_position[0] <= right and top <= next_position[1] <= bottom):
                continue
            if not track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=current,
                end=next_position,
                width_mm=TRACK_WIDTH_MM,
                source_pads=endpoint_ids,
                edge=edge,
                obstacles=spatial.query_segment(current, next_position),
            ):
                continue
            step_cost = GRID_MM * (math.sqrt(2.0) if dx_index and dy_index else 1.0)
            candidate_cost = current_cost + step_cost
            if candidate_cost + 1e-9 >= cost.get(next_state, math.inf):
                continue
            cost[next_state] = candidate_cost
            previous[next_state] = state
            estimate = candidate_cost + distance(next_position, end)
            heapq.heappush(queue, (estimate, candidate_cost, next_state))

        # When the single-layer decomposition cannot cross a component-dense
        # corridor, permit a via anywhere that is legal.  The high transition
        # cost keeps the number of vias low while still allowing the route to
        # weave through complementary openings on F.Cu and B.Cu.
        other_layer = B if layer == F else F
        via_state = (ix, iy, other_layer)
        if (
            signal_via_is_clear(
                net_name=net_name,
                position=current,
                endpoint_pad_ids=endpoint_ids,
                edge=edge,
                obstacles=spatial.query_point(current),
            )
            and current_cost + 2.5 < cost.get(via_state, math.inf)
        ):
            cost[via_state] = current_cost + 2.5
            previous[via_state] = state
            heapq.heappush(
                queue,
                (current_cost + 2.5 + distance(current, end), current_cost + 2.5, via_state),
            )

    if goal_state is None:
        for debug_layer in (F, B):
            layer_states = [state for state in cost if state[2] == debug_layer]
            if layer_states:
                positions = [
                    (start[0] + state[0] * GRID_MM, start[1] + state[1] * GRID_MM)
                    for state in layer_states
                ]
                print(
                    f"Search {net_name} {'F.Cu' if debug_layer == F else 'B.Cu'}: "
                    f"states={len(layer_states)}, x={min(p[0] for p in positions):.2f}..{max(p[0] for p in positions):.2f}, "
                    f"y={min(p[1] for p in positions):.2f}..{max(p[1] for p in positions):.2f}, "
                    f"closest={min(distance(p, end) for p in positions):.2f} mm"
                )
        return None
    states = [goal_state]
    while states[-1] != start_state:
        states.append(previous[states[-1]])
    states.reverse()
    raw = [
        (start[0] + state[0] * GRID_MM, start[1] + state[1] * GRID_MM, state[2])
        for state in states
    ]
    raw.append((end[0], end[1], end_layer))

    # Simplify only within one layer; a repeated position with a layer change
    # is retained as the explicit via site.
    result: list[tuple[float, float, int]] = []
    section: list[tuple[float, float]] = []
    section_layer = raw[0][2]
    for entry in raw:
        if entry[2] != section_layer:
            for position in simplify_grid_path(section):
                result.append((position[0], position[1], section_layer))
            result.append((entry[0], entry[1], entry[2]))
            section = [(entry[0], entry[1])]
            section_layer = entry[2]
        else:
            section.append((entry[0], entry[1]))
    for position in simplify_grid_path(section):
        candidate = (position[0], position[1], section_layer)
        if not result or candidate != result[-1]:
            result.append(candidate)
    return tuple(result)


def add_route(
    board: pcbnew.BOARD,
    net_name: str,
    route: tuple[tuple[float, float, int], ...],
    obstacles: list[CopperObstacle],
) -> tuple[int, int]:
    net = board.FindNet(net_name)
    if net is None:
        raise RuntimeError(f"LF control net is missing: {net_name}")
    tracks = 0
    vias = 0
    for index in range(len(route) - 1):
        start = route[index]
        end = route[index + 1]
        if start[2] != end[2]:
            if distance((start[0], start[1]), (end[0], end[1])) > 0.001:
                raise RuntimeError(f"LF layer change moved position on {net_name}")
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(point(start[0], start[1]))
            via.SetWidth(pcbnew.FromMM(VIA_DIAMETER_MM))
            via.SetDrill(pcbnew.FromMM(VIA_DRILL_MM))
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetLayerPair(F, B)
            via.SetNet(net)
            via.SetLocked(True)
            board.Add(via)
            obstacles.append(CopperObstacle(net_name, "via", ((start[0], start[1]), VIA_DIAMETER_MM / 2.0), via))
            vias += 1
            continue
        if distance((start[0], start[1]), (end[0], end[1])) <= 0.001:
            continue
        segment = pcbnew.PCB_TRACK(board)
        segment.SetStart(point(start[0], start[1]))
        segment.SetEnd(point(end[0], end[1]))
        segment.SetWidth(pcbnew.FromMM(TRACK_WIDTH_MM))
        segment.SetLayer(start[2])
        segment.SetNet(net)
        segment.SetLocked(True)
        board.Add(segment)
        obstacles.append(
            CopperObstacle(
                net_name,
                "track",
                ((start[0], start[1]), (end[0], end[1]), TRACK_WIDTH_MM / 2.0, start[2]),
                segment,
            )
        )
        tracks += 1
    return tracks, vias


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
    edge = board_rect(board)
    obstacles = existing_obstacles(board)
    total_tracks = 0
    total_vias = 0
    for net_name, start_ref, start_number, end_ref, end_number in CONNECTIONS:
        start_pad = pad_by_reference(board, start_ref, start_number)
        end_pad = pad_by_reference(board, end_ref, end_number)
        if start_pad.GetNetname() != net_name or end_pad.GetNetname() != net_name:
            raise RuntimeError(f"LF endpoint net mismatch for {net_name}")
        if already_connected(board, start_pad, end_pad):
            print(f"Already connected: {net_name}")
            continue
        route = find_route(
            net_name=net_name,
            start_pad=start_pad,
            end_pad=end_pad,
            edge=edge,
            obstacles=obstacles,
        )
        if route is None:
            raise RuntimeError(f"No DRC-aware outer-layer route found for {net_name}")
        tracks, vias = add_route(board, net_name, route, obstacles)
        total_tracks += tracks
        total_vias += vias
        print(f"Routed {net_name}: segments={tracks}, vias={vias}")

    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    if len(list(reloaded.GetFootprints())) != 266:
        raise RuntimeError("LF global route save/reload changed the footprint count")
    print(
        f"Saved LF-global routed PCB: {output_path}; segments={total_tracks}; vias={total_vias}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
