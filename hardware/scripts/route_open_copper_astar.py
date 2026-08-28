"""Route DRC-reported open copper endpoints on a common outer layer."""

from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path
import re
import shutil

import pcbnew

import route_lf_global as maze
import route_plane_fanouts as plane
from route_plane_fanouts import board_rect, existing_obstacles


NET_RE = re.compile(r"\[([^\]]+)\]")


def item_layers(description: str) -> set[int]:
    if (
        "F.Cu - B.Cu" in description
        or "*.Cu" in description
        or description.startswith("Durchsteckpad")
    ):
        return {pcbnew.F_Cu, pcbnew.B_Cu}
    result: set[int] = set()
    if "F.Cu" in description:
        result.add(pcbnew.F_Cu)
    if "B.Cu" in description:
        result.add(pcbnew.B_Cu)
    # KiCad's DRC report uses the user-facing inner-layer names from this
    # project ("GND" and "PWR") rather than the canonical In1/In2 names.
    if "In1.Cu" in description or " auf GND" in description:
        result.add(pcbnew.In1_Cu)
    if "In2.Cu" in description or " auf PWR" in description:
        result.add(pcbnew.In2_Cu)
    return result


def escape_paths_to_vias(
    *,
    net_name: str,
    start: tuple[float, float],
    layer: int,
    edge,
    obstacles,
    maximum_paths: int = 4,
) -> list[tuple[tuple[tuple[float, float], ...], tuple[float, float]]]:
    """Find a few short, DRC-aware escapes from a copper endpoint to a via."""
    local_obstacles = maze.nearby_obstacles(obstacles, start, 11.5)
    spatial = maze.SpatialIndex(local_obstacles)
    # DRC cleanup starts at endpoints which can already be inside another
    # item's clearance halo.  Permit only the first millimetre to leave that
    # pre-existing cage; via placement and the remainder of the route still
    # use the full obstacle set.
    start_blockers = {
        id(obstacle)
        for obstacle in local_obstacles
        if maze.obstacle_rect(obstacle)
        .expanded(maze.DIFFERENT_NET_CLEARANCE_MM)
        .contains(start)
    }
    step = 0.20
    maximum_radius = 10.0
    queue: list[tuple[float, int, int]] = [(0.0, 0, 0)]
    cost: dict[tuple[int, int], float] = {(0, 0): 0.0}
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    result: list[tuple[tuple[tuple[float, float], ...], tuple[float, float]]] = []
    result_positions: list[tuple[float, float]] = []
    directions = (
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 1),
        (1, -1),
        (-1, 1),
        (-1, -1),
    )
    while queue and len(cost) < 180_000:
        current_cost, ix, iy = heapq.heappop(queue)
        key = (ix, iy)
        if current_cost > cost.get(key, math.inf) + 1e-9:
            continue
        current = (start[0] + ix * step, start[1] + iy * step)
        if current_cost >= 0.60 and maze.signal_via_is_clear(
            net_name=net_name,
            position=current,
            endpoint_pad_ids=set(),
            edge=edge,
            obstacles=spatial.query_point(current),
        ):
            if all(math.dist(current, position) >= 0.90 for position in result_positions):
                keys = [key]
                while keys[-1] != (0, 0):
                    keys.append(previous[keys[-1]])
                keys.reverse()
                points = tuple(
                    maze.simplify_grid_path(
                        [(start[0] + x * step, start[1] + y * step) for x, y in keys]
                    )
                )
                result.append((points, current))
                result_positions.append(current)
                if len(result) >= maximum_paths:
                    return result
        for dx_index, dy_index in directions:
            next_key = (ix + dx_index, iy + dy_index)
            next_position = (
                start[0] + next_key[0] * step,
                start[1] + next_key[1] * step,
            )
            if math.dist(start, next_position) > maximum_radius:
                continue
            segment_obstacles = spatial.query_segment(current, next_position)
            if current_cost < 1.20:
                segment_obstacles = [
                    obstacle
                    for obstacle in segment_obstacles
                    if id(obstacle) not in start_blockers
                ]
            if not maze.track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=current,
                end=next_position,
                width_mm=maze.TRACK_WIDTH_MM,
                source_pads=set(),
                edge=edge,
                obstacles=segment_obstacles,
            ):
                continue
            step_cost = step * (math.sqrt(2.0) if dx_index and dy_index else 1.0)
            candidate_cost = current_cost + step_cost
            if candidate_cost + 1e-9 >= cost.get(next_key, math.inf):
                continue
            cost[next_key] = candidate_cost
            previous[next_key] = key
            heapq.heappush(queue, (candidate_cost, *next_key))
    return result


def find_alternate_layer_route(
    *,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    native_layer: int,
    route_layer: int,
    edge,
    obstacles,
    expansion: float,
) -> tuple[tuple[float, float, int], ...] | None:
    """Escape twice and use another copper layer for the long section."""
    start_escapes = escape_paths_to_vias(
        net_name=net_name,
        start=start,
        layer=native_layer,
        edge=edge,
        obstacles=obstacles,
    )
    if not start_escapes:
        return None
    end_escapes = escape_paths_to_vias(
        net_name=net_name,
        start=end,
        layer=native_layer,
        edge=edge,
        obstacles=obstacles,
    )
    pairs = sorted(
        (
            math.dist(start, start_via) + math.dist(start_via, end_via) + math.dist(end_via, end),
            start_path,
            start_via,
            end_path,
            end_via,
        )
        for start_path, start_via in start_escapes
        for end_path, end_via in end_escapes
        if math.dist(start_via, end_via) >= 0.8
    )
    for _, start_path, start_via, end_path, end_via in pairs:
        middle = maze.find_fixed_layer_path(
            net_name=net_name,
            start=start_via,
            end=end_via,
            layer=route_layer,
            endpoint_pad_ids=set(),
            edge=edge,
            obstacles=obstacles,
            expansion=expansion,
        )
        if middle is None:
            continue
        route: list[tuple[float, float, int]] = [
            (x, y, native_layer) for x, y in start_path
        ]
        route.append((start_via[0], start_via[1], route_layer))
        route.extend((x, y, route_layer) for x, y in middle[1:])
        route.append((end_via[0], end_via[1], native_layer))
        route.extend((x, y, native_layer) for x, y in reversed(end_path[:-1]))
        return tuple(route)
    return None


def find_layer_transition_route(
    *,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    start_layer: int,
    end_layer: int,
    edge,
    obstacles,
    expansion: float,
) -> tuple[tuple[float, float, int], ...] | None:
    """Connect endpoints on opposite outer layers using one clear via escape."""
    start_escapes = escape_paths_to_vias(
        net_name=net_name,
        start=start,
        layer=start_layer,
        edge=edge,
        obstacles=obstacles,
        maximum_paths=8,
    )
    end_escapes = escape_paths_to_vias(
        net_name=net_name,
        start=end,
        layer=end_layer,
        edge=edge,
        obstacles=obstacles,
        maximum_paths=8,
    )
    pairs = sorted(
        (
            math.dist(start_via, end_via),
            start_path,
            start_via,
            end_path,
            end_via,
        )
        for start_path, start_via in start_escapes
        for end_path, end_via in end_escapes
    )
    for _, start_path, start_via, end_path, end_via in pairs:
        middle = maze.find_fixed_layer_path(
            net_name=net_name,
            start=start_via,
            end=end_via,
            layer=end_layer,
            endpoint_pad_ids=set(),
            edge=edge,
            obstacles=obstacles,
            expansion=expansion,
        )
        if middle is None:
            continue
        route = [(x, y, start_layer) for x, y in start_path]
        route.append((start_via[0], start_via[1], end_layer))
        route.extend((x, y, end_layer) for x, y in middle[1:])
        route.extend((x, y, end_layer) for x, y in reversed(end_path[:-1]))
        return tuple(route)
    for _, start_path, start_via, end_path, end_via in pairs:
        middle = maze.find_fixed_layer_path(
            net_name=net_name,
            start=start_via,
            end=end_via,
            layer=start_layer,
            endpoint_pad_ids=set(),
            edge=edge,
            obstacles=obstacles,
            expansion=expansion,
        )
        if middle is None:
            continue
        route = [(x, y, start_layer) for x, y in start_path]
        route.extend((x, y, start_layer) for x, y in middle[1:])
        route.append((end_via[0], end_via[1], end_layer))
        route.extend((x, y, end_layer) for x, y in reversed(end_path[:-1]))
        return tuple(route)
    return None


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-distance", type=float, default=35.0)
    parser.add_argument("--max-attempts", type=int, default=40)
    parser.add_argument("--max-routes", type=int, default=8)
    parser.add_argument(
        "--candidate-offset",
        type=int,
        default=0,
        help="skip this many distance-sorted candidates before routing",
    )
    parser.add_argument("--grid", type=float, default=0.20)
    parser.add_argument("--width", type=float, default=0.15)
    parser.add_argument("--clearance", type=float, default=0.20)
    parser.add_argument("--expansion", type=float, default=16.0)
    parser.add_argument(
        "--max-search-states",
        type=int,
        default=600_000,
        help="cap the multilayer A* states per candidate",
    )
    parser.add_argument(
        "--net",
        action="append",
        help="Route only this net; may be repeated",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pad-obstacles-only", action="store_true")
    parser.add_argument(
        "--pads-only",
        action="store_true",
        help="only route DRC edges whose two reported endpoints are pads",
    )
    parser.add_argument(
        "--multilayer-pads",
        action="store_true",
        help="use the full F.Cu/B.Cu multi-via maze for pad-to-pad edges",
    )
    parser.add_argument(
        "--ignore-endpoint-cages",
        action="store_true",
        help="ignore obstacle halos that already contain a reported endpoint",
    )
    parser.add_argument("--all-edges", action="store_true")
    parser.add_argument("--allow-vias", action="store_true")
    parser.add_argument(
        "--allow-power-selected",
        action="store_true",
        help="allow explicitly selected power nets that are normally skipped",
    )
    parser.add_argument("--skip-zone-fill", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    if output == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    report = json.loads(args.drc.read_text(encoding="utf-8"))
    selected_nets = set(args.net or ())
    candidates = []
    for open_item in report.get("unconnected_items", []):
        items = open_item.get("items", [])
        if len(items) != 2:
            continue
        if args.pads_only and not all(
            item.get("description", "").startswith(("Pad ", "Durchsteckpad "))
            for item in items
        ):
            continue
        match = NET_RE.search(items[0].get("description", ""))
        if match is None:
            continue
        net_name = match.group(1)
        if selected_nets and net_name not in selected_nets:
            continue
        if (
            net_name in {"/GND", "/+3V3", "/+5V_RAW", "/+5V_AUX", "/VSYS"}
            and not (args.allow_power_selected and net_name in selected_nets)
        ):
            continue
        start_layers = item_layers(items[0].get("description", ""))
        end_layers = item_layers(items[1].get("description", ""))
        layers = start_layers & end_layers
        routing_layers = {pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu}
        has_layer_transition = bool(
            args.allow_vias
            and not layers
            and start_layers & routing_layers
            and end_layers & routing_layers
        )
        if not layers and not has_layer_transition:
            continue
        start = (float(items[0]["pos"]["x"]), float(items[0]["pos"]["y"]))
        end = (float(items[1]["pos"]["x"]), float(items[1]["pos"]["y"]))
        distance = math.dist(start, end)
        if distance <= args.max_distance:
            candidates.append(
                (
                    distance,
                    net_name,
                    start,
                    end,
                    layers,
                    start_layers,
                    end_layers,
                    items[0].get("uuid", ""),
                    items[1].get("uuid", ""),
                )
            )
    candidates.sort(key=lambda item: (item[0], item[1]))
    if args.candidate_offset:
        candidates = candidates[args.candidate_offset :]

    maze.GRID_MM = args.grid
    maze.TRACK_WIDTH_MM = args.width
    maze.DIFFERENT_NET_CLEARANCE_MM = args.clearance
    plane.DIFFERENT_NET_CLEARANCE_MM = args.clearance
    maze.ROUTE_EXPANSION_MM = args.expansion
    maze.MAX_ROUTE_SEARCH_STATES = args.max_search_states
    maze.MAX_FIXED_LAYER_SEARCH_STATES = args.max_search_states
    maze.AVOID_L3_ZONE_POLYS = ()
    edge = board_rect(board)
    obstacles = existing_obstacles(board)
    pads_by_uuid = {
        pad.m_Uuid.AsString(): pad
        for footprint in board.GetFootprints()
        for pad in footprint.Pads()
    }
    used_nets: set[str] = set()
    attempts = 0
    routed = 0

    def save_checkpoint() -> None:
        # Long maze searches may be stopped by an outer time limit.  Persist
        # every completed route so a later difficult candidate cannot discard
        # the useful work already completed in this batch.
        pcbnew.SaveBoard(str(output), board)

    for (
        distance,
        net_name,
        start,
        end,
        layers,
        start_layers,
        end_layers,
        start_uuid,
        end_uuid,
    ) in candidates:
        if routed >= args.max_routes or attempts >= args.max_attempts:
            break
        if not args.all_edges and net_name in used_nets:
            continue
        attempts += 1
        # Existing copper of the net being completed is a valid destination,
        # not an obstacle.  Keeping it in the maze cages the search at pads
        # and short existing stubs, which made every candidate fail before a
        # path could leave its endpoint.  Other-net copper and keepouts remain
        # fully clearance-checked; the completed batch is still accepted only
        # after KiCad DRC.
        routing_obstacles = [
            obstacle
            for obstacle in obstacles
            if (obstacle.net != net_name or obstacle.kind == "via")
            and (
                not args.pad_obstacles_only
                or obstacle.kind in {"pad", "keepout", "copper_graphic"}
            )
        ]
        if args.ignore_endpoint_cages:
            routing_obstacles = [
                obstacle
                for obstacle in routing_obstacles
                if obstacle.kind in {"pad", "via", "keepout"}
                or (
                    not maze.obstacle_rect(obstacle)
                    .expanded(args.clearance + args.width / 2.0)
                    .contains(start)
                    and not maze.obstacle_rect(obstacle)
                    .expanded(args.clearance + args.width / 2.0)
                    .contains(end)
                )
            ]
        if args.multilayer_pads:
            start_pad = pads_by_uuid.get(start_uuid)
            end_pad = pads_by_uuid.get(end_uuid)
            if start_pad is not None and end_pad is not None:
                try:
                    route = maze.find_route(
                        net_name=net_name,
                        start_pad=start_pad,
                        end_pad=end_pad,
                        edge=edge,
                        obstacles=routing_obstacles,
                    )
                except RuntimeError as error:
                    print(f"MULTI_SKIPPED {net_name}: {error}", flush=True)
                    route = None
                if route is not None:
                    tracks, vias = maze.add_route(board, net_name, route, obstacles)
                    routed += 1
                    if not args.all_edges:
                        used_nets.add(net_name)
                    save_checkpoint()
                    print(
                        f"ROUTED {net_name} MULTI distance={distance:.2f} "
                        f"tracks={tracks} vias={vias}",
                        flush=True,
                    )
                    continue
        for layer in sorted(layers, key=lambda value: value != pcbnew.B_Cu):
            result = maze.find_fixed_layer_path_to_goals(
                net_name=net_name,
                start=start,
                ends=(end,),
                layer=layer,
                endpoint_pad_ids=set(),
                edge=edge,
                obstacles=routing_obstacles,
                expansion=args.expansion,
                debug_label=net_name,
            )
            if result is None:
                continue
            points, _ = result
            route = tuple((x, y, layer) for x, y in points)
            tracks, vias = maze.add_route(board, net_name, route, obstacles)
            routed += 1
            if not args.all_edges:
                used_nets.add(net_name)
            save_checkpoint()
            print(
                f"ROUTED {net_name} {board.GetLayerName(layer)} "
                f"distance={distance:.2f} tracks={tracks} vias={vias}",
                flush=True,
            )
            break
        else:
            route = None
            if args.allow_vias and not layers:
                routing_layers = {pcbnew.F_Cu, pcbnew.B_Cu}
                transition_pairs = [
                    (start_layer, end_layer)
                    for start_layer in start_layers & routing_layers
                    for end_layer in end_layers & routing_layers
                    if start_layer != end_layer
                ]
                for start_layer, end_layer in transition_pairs:
                    route = find_layer_transition_route(
                        net_name=net_name,
                        start=start,
                        end=end,
                        start_layer=start_layer,
                        end_layer=end_layer,
                        edge=edge,
                        obstacles=routing_obstacles,
                        expansion=args.expansion,
                    )
                    if route is not None:
                        break
            if args.allow_vias and len(layers) == 1:
                native_layer = next(iter(layers))
                if native_layer in {pcbnew.F_Cu, pcbnew.B_Cu}:
                    alternate_layers = [
                        pcbnew.B_Cu if native_layer == pcbnew.F_Cu else pcbnew.F_Cu,
                    ]
                    for route_layer in alternate_layers:
                        route = find_alternate_layer_route(
                            net_name=net_name,
                            start=start,
                            end=end,
                            native_layer=native_layer,
                            route_layer=route_layer,
                            edge=edge,
                            obstacles=routing_obstacles,
                            expansion=args.expansion,
                        )
                        if route is not None:
                            break
            if route is None:
                print(f"FAILED {net_name} distance={distance:.2f}", flush=True)
                continue
            tracks, vias = maze.add_route(board, net_name, route, obstacles)
            routed += 1
            if not args.all_edges:
                used_nets.add(net_name)
            save_checkpoint()
            print(
                f"ROUTED {net_name} VIA distance={distance:.2f} "
                f"tracks={tracks} vias={vias}",
                flush=True,
            )

    if not args.skip_zone_fill:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix))
    print(f"SAVED routes={routed} attempts={attempts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
