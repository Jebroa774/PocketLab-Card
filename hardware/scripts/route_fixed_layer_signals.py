"""Route short ordinary pad islands on one existing outer copper layer.

This deterministic pass is deliberately conservative: it never changes a
footprint position, never inserts a via and never uses either plane layer.
It is useful after footprint migration because many formerly routed local
connections only need a new, compact path between nearby pads.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

import route_lf_global as maze
from route_plane_fanouts import B, F, board_rect, existing_obstacles, is_through_pad, item_key, pad_layer, xy
from route_remaining_signals import (
    disconnected_pad_group_cache,
    disconnected_pad_groups,
    endpoint_candidates,
    pad_label,
    routable_nets,
)


def common_outer_layers(first: pcbnew.PAD, second: pcbnew.PAD) -> tuple[int, ...]:
    first_layer = pad_layer(first)
    second_layer = pad_layer(second)
    if first_layer is not None and second_layer is not None:
        return (first_layer,) if first_layer == second_layer else ()
    if first_layer is not None:
        return (first_layer,)
    if second_layer is not None:
        return (second_layer,)
    if is_through_pad(first) and is_through_pad(second):
        return (F, B)
    return ()


def compact_path(points: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
    """Drop repeated and exactly collinear dogleg points."""

    result: list[tuple[float, float]] = []
    for position in points:
        if result and position == result[-1]:
            continue
        result.append(position)
        while len(result) >= 3:
            a, b, c = result[-3:]
            cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if abs(cross) > 1e-9:
                break
            result.pop(-2)
    return tuple(result)


def fast_dogleg_paths(
    start: tuple[float, float],
    end: tuple[float, float],
    expansion: float,
) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Generate cheap L/Z/offset paths before invoking the grid router."""

    paths: list[tuple[tuple[float, float], ...]] = [
        (start, end),
        (start, (end[0], start[1]), end),
        (start, (start[0], end[1]), end),
    ]
    offsets = [0.5 * index for index in range(1, int(expansion / 0.5) + 1)]
    mid_x = (start[0] + end[0]) / 2.0
    mid_y = (start[1] + end[1]) / 2.0
    x_channels = [mid_x]
    y_channels = [mid_y]
    for offset in offsets:
        x_channels.extend((min(start[0], end[0]) - offset, max(start[0], end[0]) + offset))
        y_channels.extend((min(start[1], end[1]) - offset, max(start[1], end[1]) + offset))
    for x in x_channels:
        paths.append((start, (x, start[1]), (x, end[1]), end))
    for y in y_channels:
        paths.append((start, (start[0], y), (end[0], y), end))

    dx, dy = end[0] - start[0], end[1] - start[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length > 1e-9:
        nx, ny = -dy / length, dx / length
        for offset in offsets:
            for sign in (-1.0, 1.0):
                ox, oy = nx * offset * sign, ny * offset * sign
                paths.append(
                    (
                        start,
                        (start[0] + ox, start[1] + oy),
                        (end[0] + ox, end[1] + oy),
                        end,
                    )
                )
    unique: list[tuple[tuple[float, float], ...]] = []
    seen: set[tuple[tuple[float, float], ...]] = set()
    for path in paths:
        candidate = compact_path(path)
        if len(candidate) < 2 or candidate in seen:
            continue
        seen.add(candidate)
        unique.append(candidate)
    return tuple(unique)


def fast_path(
    *,
    net_name: str,
    first: pcbnew.PAD,
    second: pcbnew.PAD,
    layer: int,
    edge,
    obstacles: list,
    expansion: float,
) -> tuple[tuple[float, float], ...] | None:
    endpoint_ids = {item_key(first), item_key(second)}
    spatial = maze.SpatialIndex(obstacles)
    for path in fast_dogleg_paths(xy(first.GetPosition()), xy(second.GetPosition()), expansion):
        if all(
            maze.track_segment_is_clear(
                net_name=net_name,
                layer=layer,
                start=a,
                end=b,
                width_mm=maze.TRACK_WIDTH_MM,
                source_pads=endpoint_ids,
                edge=edge,
                obstacles=spatial.query_segment(a, b),
            )
            for a, b in zip(path, path[1:])
        ):
            return path
    return None


def route_one(
    board: pcbnew.BOARD,
    net_name: str,
    obstacles: list,
    *,
    maximum_endpoint_pairs: int,
    expansion: float,
    endpoint_pair: frozenset[str] | None,
    fast_only: bool,
) -> tuple[int, int, str] | None:
    board.BuildConnectivity()
    groups = disconnected_pad_groups(board, net_name)
    if len(groups) < 2:
        return None
    edge = board_rect(board)
    candidates = endpoint_candidates(groups)
    if endpoint_pair is not None:
        candidates = [
            candidate
            for candidate in candidates
            if frozenset((pad_label(candidate[1]), pad_label(candidate[2]))) == endpoint_pair
        ]
    for _, first, second in candidates[:maximum_endpoint_pairs]:
        endpoint_ids = {item_key(first), item_key(second)}
        for layer in common_outer_layers(first, second):
            quick = fast_path(
                net_name=net_name,
                first=first,
                second=second,
                layer=layer,
                edge=edge,
                obstacles=obstacles,
                expansion=expansion,
            )
            if quick is not None:
                route = tuple((x, y, layer) for x, y in quick)
                tracks, vias = maze.add_route(board, net_name, route, obstacles)
                layer_name = "F.Cu" if layer == F else "B.Cu"
                return tracks, vias, f"{pad_label(first)} -> {pad_label(second)} on {layer_name} (fast)"
            if fast_only:
                continue
            result = maze.find_fixed_layer_path_to_goals(
                net_name=net_name,
                start=(pcbnew.ToMM(first.GetPosition().x), pcbnew.ToMM(first.GetPosition().y)),
                ends=((pcbnew.ToMM(second.GetPosition().x), pcbnew.ToMM(second.GetPosition().y)),),
                layer=layer,
                endpoint_pad_ids=endpoint_ids,
                edge=edge,
                obstacles=obstacles,
                expansion=expansion,
            )
            if result is None:
                continue
            points, _ = result
            route = tuple((x, y, layer) for x, y in points)
            tracks, vias = maze.add_route(board, net_name, route, obstacles)
            layer_name = "F.Cu" if layer == F else "B.Cu"
            return tracks, vias, f"{pad_label(first)} -> {pad_label(second)} on {layer_name}"
    return None


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", action="append", default=[])
    parser.add_argument(
        "--allow-protected-requested",
        action="store_true",
        help="Allow an explicitly requested reviewed power/critical net",
    )
    parser.add_argument("--max-routes", type=int, default=24)
    parser.add_argument("--repeat-per-net", type=int, default=2)
    parser.add_argument("--maximum-endpoint-pairs", type=int, default=8)
    parser.add_argument("--grid", type=float, default=0.25)
    parser.add_argument("--track-width", type=float, default=0.20)
    parser.add_argument("--clearance", type=float, default=0.20)
    parser.add_argument("--expansion", type=float, default=8.0)
    parser.add_argument(
        "--fast-only",
        action="store_true",
        help="try direct geometric doglegs only and skip the expensive grid search",
    )
    parser.add_argument(
        "--endpoint-pair",
        help="Restrict routing to one unordered pair such as R601.1,R610.1",
    )
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

    maze.GRID_MM = args.grid
    maze.TRACK_WIDTH_MM = args.track_width
    maze.DIFFERENT_NET_CLEARANCE_MM = args.clearance
    maze.AVOID_L3_ZONE_POLYS = ()
    maze.ROUTING_LAYERS = (F, B)

    board = pcbnew.LoadBoard(str(input_path))
    groups = disconnected_pad_group_cache(board)
    if args.allow_protected_requested and args.net:
        selected = []
        for requested in args.net:
            name = requested if requested.startswith("/") else f"/{requested}"
            if name not in groups:
                raise RuntimeError(f"Requested net is absent: {name}")
            if len(groups[name]) > 1:
                selected.append(name)
    else:
        selected = routable_nets(board, tuple(args.net), groups)
    selected.sort(key=lambda name: (endpoint_candidates(groups[name])[0][0], name))
    obstacles = existing_obstacles(board)
    endpoint_pair = None
    if args.endpoint_pair:
        labels = [item.strip() for item in args.endpoint_pair.split(",") if item.strip()]
        if len(labels) != 2:
            raise RuntimeError("--endpoint-pair requires exactly two REF.PAD labels")
        endpoint_pair = frozenset(labels)
    routed = 0
    total_tracks = 0
    for net_name in selected:
        for _ in range(args.repeat_per_net):
            if routed >= args.max_routes:
                break
            result = route_one(
                board,
                net_name,
                obstacles,
                maximum_endpoint_pairs=args.maximum_endpoint_pairs,
                expansion=args.expansion,
                endpoint_pair=endpoint_pair,
                fast_only=args.fast_only,
            )
            if result is None:
                break
            tracks, vias, endpoints = result
            routed += 1
            total_tracks += tracks
            print(f"ROUTED {net_name}: {endpoints}; segments={tracks}; vias={vias}", flush=True)
        if routed >= args.max_routes:
            break

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    print(f"Saved fixed-layer candidate: {output_path}; routes={routed}; segments={total_tracks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
