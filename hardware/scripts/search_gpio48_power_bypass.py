"""Find a short outer-layer bypass for the GPIO48 In2 power-plane cut.

This is a read-only diagnostic.  It reports a route between two existing
GPIO48 In2 vertices; the corresponding In2 subpath can then be replaced by
two microvias and the reported outer-layer track.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict, deque
from pathlib import Path

import pcbnew

import route_lf_global as maze
import route_plane_fanouts as fanout
from restore_split_power_islands import microvia_obstacles


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return (position.x / 1_000_000.0, position.y / 1_000_000.0)


def layer_microvia_obstacles(
    obstacles: list[fanout.CopperObstacle], layer: int
) -> list[fanout.CopperObstacle]:
    touched = {pcbnew.In2_Cu, layer}
    result: list[fanout.CopperObstacle] = []
    for obstacle in obstacles:
        if obstacle.kind == "pad":
            if touched.intersection(set(obstacle.owner.GetLayerSet().Seq())):
                result.append(obstacle)
        elif obstacle.kind == "track":
            if obstacle.geometry[3] in touched:
                result.append(obstacle)
        elif obstacle.kind == "copper_graphic":
            if obstacle.geometry[1] in touched:
                result.append(obstacle)
        elif obstacle.kind == "keepout":
            if touched.intersection(obstacle.geometry[1]):
                result.append(obstacle)
        else:
            result.append(obstacle)
    return result


def ordered_in2_path(
    board: pcbnew.BOARD, net_name: str, origin: tuple[float, float]
) -> tuple[list[tuple[float, float]], dict[frozenset[tuple[float, float]], pcbnew.PCB_TRACK]]:
    graph: dict[tuple[float, float], set[tuple[float, float]]] = defaultdict(set)
    items: dict[frozenset[tuple[float, float]], pcbnew.PCB_TRACK] = {}
    for item in board.GetTracks():
        if (
            item.GetNetname() != net_name
            or item.Type() != pcbnew.PCB_TRACE_T
            or item.GetLayer() != pcbnew.In2_Cu
        ):
            continue
        start = xy(item.GetStart())
        end = xy(item.GetEnd())
        graph[start].add(end)
        graph[end].add(start)
        items[frozenset((start, end))] = item
    if origin not in graph:
        raise RuntimeError(f"Origin {origin} is not an In2 route vertex")
    leaves = [node for node, neighbours in graph.items() if len(neighbours) == 1]
    target = max(leaves, key=lambda node: math.dist(origin, node))
    previous: dict[tuple[float, float], tuple[float, float] | None] = {origin: None}
    queue = deque((origin,))
    while queue:
        current = queue.popleft()
        if current == target:
            break
        for neighbour in graph[current]:
            if neighbour not in previous:
                previous[neighbour] = current
                queue.append(neighbour)
    path: list[tuple[float, float]] = []
    current: tuple[float, float] | None = target
    while current is not None:
        path.append(current)
        current = previous[current]
    path.reverse()
    return path, items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board.resolve()))
    board.BuildConnectivity()
    net_name = "/GPIO48"
    path, _ = ordered_in2_path(board, net_name, (65.645, 31.49))
    local = [position for position in path if 60.0 <= position[0] <= 76.0 and 30.0 <= position[1] <= 58.5]
    print(f"LOCAL PATH ({len(local)} vertices): {local}")

    fanout.VIA_DIAMETER_MM = 0.30
    fanout.VIA_DRILL_MM = 0.10
    fanout.DIFFERENT_NET_CLEARANCE_MM = 0.20
    fanout.PLANE_LAYER[net_name] = pcbnew.In2_Cu
    maze.TRACK_WIDTH_MM = 0.15
    maze.GRID_MM = 0.25
    maze.DIFFERENT_NET_CLEARANCE_MM = 0.20
    edge = fanout.board_rect(board)
    obstacles = fanout.existing_obstacles(board)
    # Existing copper of the net is a legal launch/merge target.  The generic
    # maze checker ignores same-net tracks but conservatively treats vias as
    # obstacles, so remove all GPIO48 copper from the routing obstacle view.
    route_obstacles = [obstacle for obstacle in obstacles if obstacle.net != net_name]
    source_pads: set[str] = set()
    net_pads = [
        pad
        for footprint in board.GetFootprints()
        for pad in footprint.Pads()
        if pad.GetNetname() == net_name
    ]

    for layer in (pcbnew.B_Cu, pcbnew.F_Cu):
        via_obstacles = (
            microvia_obstacles(obstacles)
            if layer == pcbnew.B_Cu
            else layer_microvia_obstacles(obstacles, layer)
        )
        valid = [
            position
            for position in local
            if fanout.via_point_is_clear(
                net_name=net_name,
                end=position,
                source_pads=source_pads,
                edge=edge,
                obstacles=via_obstacles,
            )
        ]
        launch = (65.645, 31.49)
        launch_steps = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            destination = (launch[0] + 0.25 * dx, launch[1] + 0.25 * dy)
            if fanout.track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=launch,
                end=destination,
                width_mm=0.15,
                source_pads=source_pads,
                edge=edge,
                obstacles=route_obstacles,
            ):
                launch_steps.append(destination)
        print(f"{board.GetLayerName(layer)} LAUNCH STEPS: {launch_steps}")
        print(f"{board.GetLayerName(layer)} VIA VERTICES: {valid}")
        # The route already owns a through via at its first vertex, so this
        # is also a legal outer-layer start without adding another via.
        before = [(65.645, 31.49), *[
            position for position in valid if position[1] <= 35.50
        ]]
        after_vertices = [position for position in local if position[1] >= 36.75]
        after_links: dict[tuple[float, float], tuple[float, float]] = {}
        # The exact In2 vertices after the +5-V neck can be blocked on B.Cu.
        # Search a small halo and retain sites that can reach the existing
        # In2 path with a short, clearance-clean stub.
        for x_index in range(round(60.0 / 0.25), round(76.0 / 0.25) + 1):
            for y_index in range(round(36.5 / 0.25), round(58.5 / 0.25) + 1):
                candidate = (x_index * 0.25, y_index * 0.25)
                if not fanout.via_point_is_clear(
                    net_name=net_name,
                    end=candidate,
                    source_pads=source_pads,
                    edge=edge,
                    obstacles=via_obstacles,
                ):
                    continue
                for vertex in sorted(after_vertices, key=lambda p: math.dist(candidate, p)):
                    if math.dist(candidate, vertex) > 2.0:
                        break
                    if fanout.track_segment_is_clear(
                        net_name=net_name,
                        layer=pcbnew.In2_Cu,
                        start=candidate,
                        end=vertex,
                        width_mm=0.15,
                        source_pads=source_pads,
                        edge=edge,
                        obstacles=obstacles,
                    ):
                        after_links[candidate] = vertex
                        break
        after = list(after_links)
        print(
            f"{board.GetLayerName(layer)} AFTER SITES ({len(after)}): "
            f"{[(site, after_links[site]) for site in after[:30]]}"
        )
        for start in sorted(before, key=lambda p: (-p[1], -p[0])):
            ends = tuple(sorted(after, key=lambda p: math.dist(start, p)))
            if not ends:
                continue
            routed = maze.find_fixed_layer_path_to_goals(
                net_name=net_name,
                start=start,
                ends=ends,
                layer=layer,
                endpoint_pad_ids=source_pads,
                edge=edge,
                obstacles=route_obstacles,
                expansion=10.0,
            )
            if routed is None:
                continue
            route, goal_index = routed
            print(
                f"FOUND {board.GetLayerName(layer)} {start} -> {ends[goal_index]}: "
                f"{route}; In2 stub -> {after_links[ends[goal_index]]}"
            )
            return 0
        maze.ROUTING_LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
        maze.ROUTE_EXPANSION_MM = 10.0
        maze.MAX_ROUTE_SEARCH_STATES = 220_000
        maze.VIA_DIAMETER_MM = 0.45
        maze.VIA_DRILL_MM = 0.20
        launch = (65.645, 31.49)
        for end in sorted(after, key=lambda position: math.dist(launch, position))[:16]:
            for start_layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                routed = maze.find_route(
                    net_name=net_name,
                    start_pad=net_pads[0],
                    end_pad=net_pads[-1],
                    edge=edge,
                    obstacles=route_obstacles,
                    start_override=launch,
                    end_override=end,
                    start_layer_override=start_layer,
                    end_layer_override=layer,
                )
                if routed is None:
                    continue
                print(
                    f"FOUND MULTILAYER {board.GetLayerName(start_layer)} -> "
                    f"{board.GetLayerName(layer)} {launch} -> {end}: {routed}; "
                    f"In2 stub -> {after_links[end]}"
                )
                return 0
    print("NO BYPASS")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
