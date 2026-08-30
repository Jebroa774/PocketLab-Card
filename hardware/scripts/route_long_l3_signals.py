"""Route long ordinary header nets with one reviewed L3 signal trunk.

Each selected island must join one through-hole pad to one one-sided SMD pad.
The SMD endpoint receives a short outer-layer escape and one ordinary through
via; the long section then runs on In2.Cu/PWR directly into the through-hole
pad.  KiCad refills the +5 V zones around the new signal copper, and DRC is the
acceptance check.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

import route_lf_global as maze
from route_plane_fanouts import board_rect, existing_obstacles, is_through_pad, item_key, pad_layer, xy
from route_remaining_signals import disconnected_pad_groups, endpoint_candidates, pad_label


def route_net(
    board: pcbnew.BOARD,
    net_name: str,
    obstacles: list,
    *,
    expansion: float,
    routing_mode: str,
) -> tuple[int, int, str] | None:
    board.BuildConnectivity()
    groups = disconnected_pad_groups(board, net_name)
    if len(groups) < 2:
        return None
    edge = board_rect(board)
    for _, first, second in endpoint_candidates(groups):
        if is_through_pad(first) and pad_layer(second) is not None:
            through_pad, surface_pad = first, second
        elif is_through_pad(second) and pad_layer(first) is not None:
            through_pad, surface_pad = second, first
        else:
            continue

        endpoint_ids = {item_key(through_pad), item_key(surface_pad)}
        surface_layer = pad_layer(surface_pad)
        assert surface_layer is not None
        if routing_mode == "outer":
            middle_result = maze.find_fixed_layer_path_to_goals(
                net_name=net_name,
                start=xy(through_pad.GetPosition()),
                ends=(xy(surface_pad.GetPosition()),),
                layer=surface_layer,
                endpoint_pad_ids=endpoint_ids,
                edge=edge,
                obstacles=obstacles,
                expansion=expansion,
            )
            if middle_result is None:
                continue
            middle, _ = middle_result
            route = tuple((position[0], position[1], surface_layer) for position in middle)
            tracks, vias = maze.add_route(board, net_name, route, obstacles)
            return tracks, vias, f"{pad_label(through_pad)} -> {pad_label(surface_pad)}"

        escapes = maze.find_escape_paths(
            net_name=net_name,
            pad=surface_pad,
            endpoint_pad_ids=endpoint_ids,
            edge=edge,
            obstacles=obstacles,
            maximum_paths=16,
        )
        if not escapes:
            continue
        escape_ends = tuple(path[-1] for path in escapes)
        trunk_layer = (
            pcbnew.In2_Cu
            if routing_mode == "power"
            else (pcbnew.B_Cu if surface_layer == pcbnew.F_Cu else pcbnew.F_Cu)
        )
        middle_result = maze.find_fixed_layer_path_to_goals(
            net_name=net_name,
            start=xy(through_pad.GetPosition()),
            ends=escape_ends,
            layer=trunk_layer,
            endpoint_pad_ids=endpoint_ids,
            edge=edge,
            obstacles=obstacles,
            expansion=expansion,
        )
        if middle_result is None:
            continue
        middle, escape_index = middle_result
        escape = escapes[escape_index]
        route = [(position[0], position[1], trunk_layer) for position in middle]
        route.append((escape[-1][0], escape[-1][1], surface_layer))
        route.extend(
            (position[0], position[1], surface_layer)
            for position in reversed(escape[:-1])
        )
        tracks, vias = maze.add_route(board, net_name, tuple(route), obstacles)
        return tracks, vias, f"{pad_label(through_pad)} -> {pad_label(surface_pad)}"
    return None


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", action="append", required=True)
    parser.add_argument("--grid", type=float, default=0.50)
    parser.add_argument("--track-width", type=float, default=0.20)
    parser.add_argument("--via-diameter", type=float, default=0.50)
    parser.add_argument("--via-drill", type=float, default=0.30)
    parser.add_argument("--clearance", type=float, default=0.25)
    parser.add_argument("--expansion", type=float, default=10.0)
    parser.add_argument(
        "--routing-mode",
        choices=("power", "outer", "opposite"),
        default="power",
        help="use an In2.Cu trunk or stay on the SMD endpoint's outer layer",
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
    maze.VIA_DIAMETER_MM = args.via_diameter
    maze.VIA_DRILL_MM = args.via_drill
    maze.DIFFERENT_NET_CLEARANCE_MM = args.clearance
    maze.ROUTING_LAYERS = (pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)

    board = pcbnew.LoadBoard(str(input_path))
    # Filled power zones are not fixed copper obstacles: KiCad carves their
    # configured clearance around signal tracks and vias on refill.  Treating
    # their stale pre-route fill as immutable makes every long L3 route appear
    # blocked even though the resulting board is electrically valid.
    maze.AVOID_L3_ZONE_POLYS = ()
    obstacles = existing_obstacles(board)
    routed = 0
    total_tracks = 0
    total_vias = 0
    for name in args.net:
        net_name = name if name.startswith("/") else f"/{name}"
        result = route_net(
            board,
            net_name,
            obstacles,
            expansion=args.expansion,
            routing_mode=args.routing_mode,
        )
        if result is None:
            print(f"SKIPPED {net_name}", flush=True)
            continue
        tracks, vias, endpoints = result
        routed += 1
        total_tracks += tracks
        total_vias += vias
        print(
            f"ROUTED {net_name}: {endpoints}; segments={tracks}; vias={vias}",
            flush=True,
        )

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    print(
        f"Saved long-L3 candidate: {output_path}; routes={routed}; "
        f"segments={total_tracks}; vias={total_vias}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
