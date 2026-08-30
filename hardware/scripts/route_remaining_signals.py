"""Route ordinary, non-critical unfinished nets in deterministic small passes.

Critical power, USB, RF, resonant and oscillator nets stay owned by their
reviewed manual routing stages.  This helper connects one island at a time on
ordinary digital/control nets, supports both SMD and through-hole endpoints,
and always refills the four-layer plane zones before saving.  KiCad DRC is the
acceptance check for every generated candidate PCB.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil

import pcbnew

import route_lf_global as maze
import route_pcb
import route_plane_fanouts as fanout
from route_plane_fanouts import B, F, board_rect, existing_obstacles, item_key, pad_layer, xy


ADDITIONAL_PROTECTED_NETS = frozenset({"NFC_DVDD"})


def physical_name(net_name: str) -> str:
    return net_name[1:] if net_name.startswith("/") else net_name


def pad_label(pad: pcbnew.PAD) -> str:
    return f"{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}"


def connected_signature(board: pcbnew.BOARD, pad: pcbnew.PAD) -> frozenset[str]:
    items = board.GetConnectivity().GetConnectedItems(pad)
    return frozenset(item_key(item) for item in items)


def disconnected_pad_groups(board: pcbnew.BOARD, net_name: str) -> list[list[pcbnew.PAD]]:
    groups: dict[frozenset[str], list[pcbnew.PAD]] = {}
    seen_pads: set[str] = set()
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if pad.GetNetname() != net_name or item_key(pad) in seen_pads:
                continue
            seen_pads.add(item_key(pad))
            groups.setdefault(connected_signature(board, pad), []).append(pad)
    return list(groups.values())


def disconnected_pad_group_cache(
    board: pcbnew.BOARD,
) -> dict[str, list[list[pcbnew.PAD]]]:
    """Build disconnected pad groups for every net in one footprint pass."""

    board.BuildConnectivity()
    groups_by_net: dict[str, dict[frozenset[str], list[pcbnew.PAD]]] = {}
    seen_pads: set[str] = set()
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            net_name = pad.GetNetname()
            key = item_key(pad)
            if not net_name or key in seen_pads:
                continue
            seen_pads.add(key)
            groups_by_net.setdefault(net_name, {}).setdefault(
                connected_signature(board, pad), []
            ).append(pad)
    return {
        net_name: list(signature_groups.values())
        for net_name, signature_groups in groups_by_net.items()
    }


def endpoint_layer_choices(pad: pcbnew.PAD) -> tuple[int, ...]:
    layer = pad_layer(pad)
    return (layer,) if layer is not None else (F, B)


def endpoint_candidates(groups: list[list[pcbnew.PAD]]) -> list[tuple[float, pcbnew.PAD, pcbnew.PAD]]:
    candidates: list[tuple[float, pcbnew.PAD, pcbnew.PAD]] = []
    for left_index, left_group in enumerate(groups):
        for right_group in groups[left_index + 1 :]:
            for left in left_group:
                for right in right_group:
                    candidates.append((math.dist(xy(left.GetPosition()), xy(right.GetPosition())), left, right))
    candidates.sort(key=lambda entry: (entry[0], pad_label(entry[1]), pad_label(entry[2])))
    return candidates


def routable_nets(
    board: pcbnew.BOARD,
    requested: tuple[str, ...],
    groups_by_net: dict[str, list[list[pcbnew.PAD]]] | None = None,
) -> list[str]:
    # Building connectivity and walking all pads are whole-board operations.
    # Cache both once during discovery instead of crossing the pcbnew boundary
    # once for every individual net.
    if groups_by_net is None:
        groups_by_net = disconnected_pad_group_cache(board)
    protected = set(route_pcb.MANUAL_LOGICAL_NETS) | set(ADDITIONAL_PROTECTED_NETS)
    board_names = sorted(groups_by_net)
    if requested:
        wanted = {name if name.startswith("/") else f"/{name}" for name in requested}
        missing = wanted.difference(board_names)
        if missing:
            raise RuntimeError(f"Requested nets are absent: {', '.join(sorted(missing))}")
        board_names = [name for name in board_names if name in wanted]
    result = []
    for name in board_names:
        if physical_name(name) in protected:
            continue
        groups = groups_by_net[name]
        if len(groups) > 1:
            result.append(name)
    return result


def route_one_island(
    board: pcbnew.BOARD,
    net_name: str,
    *,
    maximum_endpoint_pairs: int,
    use_decomposed: bool,
    decomposed_only: bool,
    endpoint_pair: frozenset[str] | None,
    reverse_endpoints: bool,
) -> tuple[int, int, str] | None:
    # A previously accepted island route changes the connectivity graph, so
    # rebuild only at the point where a new route is actually attempted.
    board.BuildConnectivity()
    groups = disconnected_pad_groups(board, net_name)
    if len(groups) < 2:
        return None
    edge = board_rect(board)
    obstacles = existing_obstacles(board)
    candidates = endpoint_candidates(groups)
    if endpoint_pair is not None:
        candidates = [
            candidate
            for candidate in candidates
            if frozenset((pad_label(candidate[1]), pad_label(candidate[2]))) == endpoint_pair
        ]
    for _, start_pad, end_pad in candidates[:maximum_endpoint_pairs]:
        if reverse_endpoints:
            start_pad, end_pad = end_pad, start_pad
        start_fixed_layer = pad_layer(start_pad)
        end_fixed_layer = pad_layer(end_pad)
        if (
            use_decomposed
            and
            len(maze.ROUTING_LAYERS) == 2
            and start_fixed_layer is not None
            and end_fixed_layer is not None
        ):
            if decomposed_only:
                route = maze.decomposed_route(
                    net_name=net_name,
                    start_pad=start_pad,
                    end_pad=end_pad,
                    edge=edge,
                    obstacles=obstacles,
                )
                if route is not None:
                    tracks, vias = maze.add_route(board, net_name, route, obstacles)
                    return tracks, vias, f"{pad_label(start_pad)} -> {pad_label(end_pad)}"
                continue
            route = maze.find_route(
                net_name=net_name,
                start_pad=start_pad,
                end_pad=end_pad,
                edge=edge,
                obstacles=obstacles,
            )
            if route is not None:
                tracks, vias = maze.add_route(board, net_name, route, obstacles)
                return tracks, vias, f"{pad_label(start_pad)} -> {pad_label(end_pad)}"
            continue
        for start_layer in endpoint_layer_choices(start_pad):
            for end_layer in endpoint_layer_choices(end_pad):
                route = maze.find_route(
                    net_name=net_name,
                    start_pad=start_pad,
                    end_pad=end_pad,
                    edge=edge,
                    obstacles=obstacles,
                    start_layer_override=start_layer,
                    end_layer_override=end_layer,
                )
                if route is None:
                    continue
                tracks, vias = maze.add_route(board, net_name, route, obstacles)
                return tracks, vias, f"{pad_label(start_pad)} -> {pad_label(end_pad)}"
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
        help="Allow explicitly requested reviewed power/critical nets",
    )
    parser.add_argument(
        "--endpoint-pair",
        help="Restrict routing to one unordered pair such as R601.1,R610.1",
    )
    parser.add_argument("--max-routes", type=int, default=8)
    parser.add_argument("--repeat-per-net", type=int, default=1)
    parser.add_argument("--maximum-endpoint-pairs", type=int, default=8)
    parser.add_argument("--track-width", type=float, default=0.20)
    parser.add_argument("--grid", type=float, default=0.25)
    parser.add_argument("--via-diameter", type=float, default=0.50)
    parser.add_argument("--via-drill", type=float, default=0.30)
    parser.add_argument("--clearance", type=float, default=0.20)
    parser.add_argument("--route-expansion", type=float, default=12.0)
    parser.add_argument("--max-search-states", type=int, default=150_000)
    parser.add_argument(
        "--inner-layer-cost",
        type=float,
        default=1.0,
        help="per-step cost multiplier for routes on In1.Cu or In2.Cu",
    )
    parser.add_argument(
        "--skip-decomposed",
        action="store_true",
        help="skip the expensive analogue-style endpoint escape search",
    )
    parser.add_argument(
        "--decomposed-only",
        action="store_true",
        help="try deterministic endpoint escapes only and skip the broad multilayer fallback",
    )
    parser.add_argument(
        "--allow-power-layer",
        action="store_true",
        help="also permit short ordinary-signal routes on L3/PWR; L2/GND remains plane-only",
    )
    parser.add_argument(
        "--allow-ground-layer",
        action="store_true",
        help="also permit ordinary-signal routes on L2/GND for candidate-only escape tests",
    )
    parser.add_argument(
        "--reverse-endpoints",
        action="store_true",
        help="reverse each selected endpoint pair before the maze search",
    )
    parser.add_argument(
        "--back-inner-only",
        action="store_true",
        help="with one enabled inner layer, route only on that layer and B.Cu",
    )
    parser.add_argument(
        "--allow-power-zone-crossing",
        action="store_true",
        help="permit candidate signal vias and tracks to cross existing In2 power fills",
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
    if args.max_routes < 1 or args.maximum_endpoint_pairs < 1 or args.repeat_per_net < 1:
        raise RuntimeError("Route and endpoint limits must be positive")

    maze.TRACK_WIDTH_MM = args.track_width
    maze.GRID_MM = args.grid
    maze.VIA_DIAMETER_MM = args.via_diameter
    maze.VIA_DRILL_MM = args.via_drill
    maze.DIFFERENT_NET_CLEARANCE_MM = args.clearance
    fanout.DIFFERENT_NET_CLEARANCE_MM = args.clearance
    maze.ROUTE_EXPANSION_MM = args.route_expansion
    maze.MAX_ROUTE_SEARCH_STATES = args.max_search_states
    maze.INNER_LAYER_COST_MULTIPLIER = args.inner_layer_cost
    if args.back_inner_only and args.allow_power_layer and not args.allow_ground_layer:
        maze.ROUTING_LAYERS = (pcbnew.In2_Cu, B)
    elif args.back_inner_only and args.allow_ground_layer and not args.allow_power_layer:
        maze.ROUTING_LAYERS = (pcbnew.In1_Cu, B)
    elif args.back_inner_only:
        raise RuntimeError("--back-inner-only requires exactly one enabled inner layer")
    elif args.allow_power_layer and args.allow_ground_layer:
        maze.ROUTING_LAYERS = (F, pcbnew.In1_Cu, pcbnew.In2_Cu, B)
    elif args.allow_power_layer:
        maze.ROUTING_LAYERS = (F, pcbnew.In2_Cu, B)
    elif args.allow_ground_layer:
        maze.ROUTING_LAYERS = (F, pcbnew.In1_Cu, B)
    else:
        maze.ROUTING_LAYERS = (F, B)

    board = pcbnew.LoadBoard(str(input_path))
    maze.AVOID_L3_ZONE_POLYS = () if args.allow_power_zone_crossing else tuple(
        zone.GetFilledPolysList(pcbnew.In2_Cu)
        for zone in board.Zones()
        if zone.GetNetname() in {"/+5V_RAW", "/+5V_AUX"}
        and zone.HasFilledPolysForLayer(pcbnew.In2_Cu)
    ) if args.allow_power_layer else ()
    discovery_groups = disconnected_pad_group_cache(board)
    if args.allow_protected_requested and args.net:
        selected = []
        for requested in args.net:
            name = requested if requested.startswith("/") else f"/{requested}"
            if name not in discovery_groups:
                raise RuntimeError(f"Requested net is absent: {name}")
            if len(discovery_groups[name]) > 1:
                selected.append(name)
    else:
        selected = routable_nets(board, tuple(args.net), discovery_groups)
    # Short local islands first.  This leaves the broad shared corridors free
    # until the compact component clusters have escaped.
    selected.sort(
        key=lambda name: (
            endpoint_candidates(discovery_groups[name])[0][0],
            name,
        )
    )
    routed = 0
    total_tracks = 0
    total_vias = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    endpoint_pair = None
    if args.endpoint_pair:
        labels = [item.strip() for item in args.endpoint_pair.split(",") if item.strip()]
        if len(labels) != 2:
            raise RuntimeError("--endpoint-pair requires exactly two REF.PAD labels")
        endpoint_pair = frozenset(labels)
    for net_name in selected:
        if routed >= args.max_routes:
            break
        for _ in range(args.repeat_per_net):
            if routed >= args.max_routes:
                break
            result = route_one_island(
                board,
                net_name,
                maximum_endpoint_pairs=args.maximum_endpoint_pairs,
                use_decomposed=not args.skip_decomposed,
                decomposed_only=args.decomposed_only,
                endpoint_pair=endpoint_pair,
                reverse_endpoints=args.reverse_endpoints,
            )
            if result is None:
                print(f"SKIPPED {net_name}", flush=True)
                break
            tracks, vias, endpoints = result
            routed += 1
            total_tracks += tracks
            total_vias += vias
            print(
                f"ROUTED {net_name}: {endpoints}; segments={tracks}; vias={vias}",
                flush=True,
            )
            # Keep every accepted route even when a later maze search reaches
            # the command time limit.  Zone filling is intentionally deferred
            # to the normal final save because it is comparatively expensive.
            pcbnew.SaveBoard(str(output_path), board)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(
        f"Saved ordinary-signal candidate: {output_path}; routes={routed}; "
        f"segments={total_tracks}; vias={total_vias}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
