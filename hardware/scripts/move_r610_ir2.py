"""Move the misplaced IR2 pulse resistor beside D2 and finish both nets."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil

import pcbnew

import route_plane_fanouts as fanout
import route_lf_global as maze
from restore_split_power_islands import filled_zone, group_at, outline_group_map


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return position.x / 1_000_000.0, position.y / 1_000_000.0


def find_footprint(board: pcbnew.BOARD, reference: str) -> pcbnew.FOOTPRINT:
    matches = [item for item in board.GetFootprints() if item.GetReference() == reference]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}, got {len(matches)}")
    return matches[0]


def find_pad(footprint: pcbnew.FOOTPRINT, number: str) -> pcbnew.PAD:
    matches = [pad for pad in footprint.Pads() if pad.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one {footprint.GetReference()}.{number}, got {len(matches)}"
        )
    return matches[0]


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
    layer: int,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def microvia_obstacles(
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    hardware_dir = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if output == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative board")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    old_via = (68.313234, 25.962374)
    removed = []
    old_items: list[pcbnew.PCB_TRACK] = []
    for item in board.GetTracks():
        if item.GetNetname() != "/+5V_RAW":
            continue
        if item.Type() == pcbnew.PCB_VIA_T:
            match = math.dist(xy(item.GetPosition()), old_via) < 0.002
        else:
            endpoints = (xy(item.GetStart()), xy(item.GetEnd()))
            match = any(math.dist(endpoint, old_via) < 0.002 for endpoint in endpoints)
        if match:
            removed.append(str(item.m_Uuid))
            old_items.append(item)
    if len(removed) != 2:
        raise RuntimeError(f"Expected old R610 track and via, removed {len(removed)}")

    r610 = find_footprint(board, "R610")
    r610.Flip(r610.GetPosition(), False)
    r610.SetOrientationDegrees(180.0)
    r610.SetPosition(point(28.75, 54.60))
    route_layer = pcbnew.B_Cu
    pad_5v = find_pad(r610, "1")
    pad_ir = find_pad(r610, "2")
    d2_ir = find_pad(find_footprint(board, "D2"), "2")
    board.BuildConnectivity()

    fanout.VIA_DIAMETER_MM = 0.30
    fanout.VIA_DRILL_MM = 0.10
    fanout.DIFFERENT_NET_CLEARANCE_MM = 0.20
    fanout.PLANE_LAYER["/+5V_RAW"] = pcbnew.In2_Cu
    edge = fanout.board_rect(board)
    obstacles = fanout.existing_obstacles(board)
    via_obstacles = microvia_obstacles(obstacles, route_layer)
    source_pads = {fanout.item_key(pad_5v)}
    zone = filled_zone(board, "/+5V_RAW")
    polygons = zone.GetFilledPolysList(pcbnew.In2_Cu)
    outline_groups = outline_group_map(board, "/+5V_RAW", polygons)
    pad_position = xy(pad_5v.GetPosition())
    candidates: list[tuple[float, tuple[float, float]]] = []
    for x_index in range(round(33.5 / 0.20), round(40.0 / 0.20) + 1):
        for y_index in range(round(53.5 / 0.20), round(58.0 / 0.20) + 1):
            candidate = (round(x_index * 0.20, 3), round(y_index * 0.20, 3))
            if group_at(candidate, polygons, outline_groups) != 0:
                continue
            if not fanout.via_point_is_clear(
                net_name="/+5V_RAW",
                end=candidate,
                source_pads=source_pads,
                edge=edge,
                obstacles=via_obstacles,
            ):
                continue
            if not fanout.track_segment_is_clear(
                net_name="/+5V_RAW",
                layer=route_layer,
                start=pad_position,
                end=candidate,
                width_mm=0.30,
                source_pads=source_pads,
                edge=edge,
                obstacles=obstacles,
            ):
                continue
            candidates.append((math.dist(pad_position, candidate), candidate))
    power_path: tuple[tuple[float, float], ...] | None = None
    if candidates:
        _, via_position = min(candidates)
        power_path = (pad_position, via_position)
    else:
        # Dense lower-edge placement may require a small detour to a legal
        # B.Cu-to-In2 landing in the same filled +5-V polygon.
        via_sites: list[tuple[float, float]] = []
        for x_index in range(round(34.0 / 0.25), round(48.0 / 0.25) + 1):
            for y_index in range(round(54.0 / 0.25), round(68.0 / 0.25) + 1):
                candidate = (x_index * 0.25, y_index * 0.25)
                if group_at(candidate, polygons, outline_groups) != 0:
                    continue
                if fanout.via_point_is_clear(
                    net_name="/+5V_RAW",
                    end=candidate,
                    source_pads=source_pads,
                    edge=edge,
                    obstacles=via_obstacles,
                ):
                    via_sites.append(candidate)
        ordered_sites = tuple(
            sorted(via_sites, key=lambda site: math.dist(pad_position, site))[:200]
        )
        direct_sites = [
            site
            for site in ordered_sites
            if fanout.track_segment_is_clear(
                net_name="/+5V_RAW",
                layer=route_layer,
                start=pad_position,
                end=site,
                width_mm=0.30,
                source_pads=source_pads,
                edge=edge,
                obstacles=obstacles,
            )
        ]
        reviewed_paths: list[
            tuple[float, tuple[tuple[float, float], ...], tuple[float, float]]
        ] = []
        for site in ordered_sites:
            if not (33.9 <= site[0] <= 34.6 and 64.5 <= site[1] <= 65.5):
                continue
            path = (
                pad_position,
                (30.2, 58.9),
                (34.0, 58.9),
                (34.0, site[1]),
                site,
            )
            if all(
                fanout.track_segment_is_clear(
                    net_name="/+5V_RAW",
                    layer=route_layer,
                    start=start,
                    end=end,
                    width_mm=0.30,
                    source_pads=source_pads,
                    edge=edge,
                    obstacles=obstacles,
                )
                for start, end in zip(path, path[1:])
            ):
                reviewed_paths.append(
                    (sum(math.dist(a, b) for a, b in zip(path, path[1:])), path, site)
                )
            elif site == (34.25, 65.0):
                for start, end in zip(path, path[1:]):
                    if fanout.track_segment_is_clear(
                        net_name="/+5V_RAW",
                        layer=route_layer,
                        start=start,
                        end=end,
                        width_mm=0.30,
                        source_pads=source_pads,
                        edge=edge,
                        obstacles=obstacles,
                    ):
                        continue
                    blockers = []
                    for obstacle in obstacles:
                        if fanout.track_segment_is_clear(
                            net_name="/+5V_RAW",
                            layer=route_layer,
                            start=start,
                            end=end,
                            width_mm=0.30,
                            source_pads=source_pads,
                            edge=edge,
                            obstacles=[obstacle],
                        ):
                            continue
                        owner = obstacle.owner
                        if isinstance(owner, pcbnew.PAD):
                            parent = owner.GetParentFootprint()
                            owner_label = f"{parent.GetReference()}.{owner.GetNumber()}"
                        else:
                            owner_label = str(type(owner).__name__)
                        blockers.append(
                            (obstacle.kind, obstacle.net, owner_label, obstacle.geometry)
                        )
                    print(f"BLOCKED reviewed +5V segment {start}->{end}: {blockers}")
        if reviewed_paths:
            _, power_path, via_position = min(reviewed_paths)
        elif direct_sites:
            via_position = direct_sites[0]
            power_path = (pad_position, via_position)
        else:
            maze.TRACK_WIDTH_MM = 0.30
            maze.GRID_MM = 0.25
            maze.DIFFERENT_NET_CLEARANCE_MM = 0.20
            routed = maze.find_fixed_layer_path_to_goals(
                net_name="/+5V_RAW",
                start=pad_position,
                ends=ordered_sites,
                layer=route_layer,
                endpoint_pad_ids=source_pads,
                edge=edge,
                obstacles=obstacles,
                expansion=6.0,
            )
            if routed is None:
                nearest = ordered_sites[0] if ordered_sites else pad_position
                blockers = [
                    (obstacle.kind, obstacle.net, obstacle.geometry)
                    for obstacle in obstacles
                    if not fanout.track_segment_is_clear(
                        net_name="/+5V_RAW",
                        layer=route_layer,
                        start=pad_position,
                        end=nearest,
                        width_mm=0.30,
                        source_pads=source_pads,
                        edge=edge,
                        obstacles=[obstacle],
                    )
                ]
                raise RuntimeError(
                    f"No reviewed-clear +5V_RAW via route beside moved R610; "
                    f"pad={pad_position}, via_sites={len(via_sites)}, nearest="
                    f"{ordered_sites[:12]}, direct_blockers={blockers}"
                )
            power_path, goal_index = routed
            via_position = ordered_sites[goal_index]

    assert power_path is not None
    for start, end in zip(power_path, power_path[1:]):
        add_track(board, "/+5V_RAW", start, end, 0.30, route_layer)
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(*via_position))
    via.SetWidth(pcbnew.FromMM(0.30))
    via.SetDrill(pcbnew.FromMM(0.10))
    via.SetViaType(pcbnew.VIATYPE_MICROVIA)
    via.SetLayerPair(pcbnew.In2_Cu, pcbnew.B_Cu)
    via.SetNet(board.FindNet("/+5V_RAW"))
    via.SetLocked(True)
    board.Add(via)

    # Refresh obstacles so the IR escape is checked against the newly added
    # +5-V route as well as the original board copper.
    obstacles = fanout.existing_obstacles(board)
    ir_start = xy(pad_ir.GetPosition())
    ir_end = xy(d2_ir.GetPosition())
    ir_sources = {fanout.item_key(pad_ir), fanout.item_key(d2_ir)}
    ir_via_position = (30.00, ir_end[1])
    ir_path = (
        ir_start,
        (29.00, ir_start[1]),
        (29.00, ir_end[1]),
        ir_via_position,
    )
    if not all(
        fanout.track_segment_is_clear(
            net_name="/IR_LED_A2",
            layer=route_layer,
            start=start,
            end=end,
            width_mm=0.60,
            source_pads=ir_sources,
            edge=edge,
            obstacles=obstacles,
        )
        for start, end in zip(ir_path, ir_path[1:])
    ):
        blockers = [
            (obstacle.kind, obstacle.net, obstacle.geometry)
            for obstacle in obstacles
            if not fanout.track_segment_is_clear(
                net_name="/IR_LED_A2",
                layer=route_layer,
                start=ir_path[1],
                end=ir_path[2],
                width_mm=0.60,
                source_pads=ir_sources,
                edge=edge,
                obstacles=[obstacle],
            )
        ]
        raise RuntimeError(
            f"R610.2-to-D2.2 route is not clearance-clean: "
            f"{ir_path}; central blockers={blockers}"
        )
    for start, end in zip(ir_path, ir_path[1:]):
        add_track(board, "/IR_LED_A2", start, end, 0.60, route_layer)
    fanout.VIA_DIAMETER_MM = 0.30
    fanout.VIA_DRILL_MM = 0.10
    fanout.PLANE_LAYER["/IR_LED_A2"] = pcbnew.In2_Cu
    if not fanout.via_point_is_clear(
        net_name="/IR_LED_A2",
        end=ir_via_position,
        source_pads=ir_sources,
        edge=edge,
        obstacles=microvia_obstacles(obstacles, route_layer),
    ):
        raise RuntimeError(f"IR_LED_A2 microvia is not clearance-clean: {ir_via_position}")
    if not fanout.track_segment_is_clear(
        net_name="/IR_LED_A2",
        layer=pcbnew.In2_Cu,
        start=ir_via_position,
        end=ir_end,
        width_mm=0.30,
        source_pads=ir_sources,
        edge=edge,
        obstacles=obstacles,
    ):
        raise RuntimeError(
            f"IR_LED_A2 In2.Cu hop is not clearance-clean: "
            f"{ir_via_position}->{ir_end}"
        )
    ir_via = pcbnew.PCB_VIA(board)
    ir_via.SetPosition(point(*ir_via_position))
    ir_via.SetWidth(pcbnew.FromMM(0.30))
    ir_via.SetDrill(pcbnew.FromMM(0.10))
    ir_via.SetViaType(pcbnew.VIATYPE_MICROVIA)
    ir_via.SetLayerPair(pcbnew.In2_Cu, pcbnew.B_Cu)
    ir_via.SetNet(board.FindNet("/IR_LED_A2"))
    ir_via.SetLocked(True)
    board.Add(ir_via)
    add_track(
        board,
        "/IR_LED_A2",
        ir_via_position,
        ir_end,
        0.30,
        pcbnew.In2_Cu,
    )

    # Removing a TRACK wrapper invalidates KiCad's Python collection view.
    # Defer both removals until all board enumeration and object creation is
    # complete, then immediately refill/save through the native board API.
    for item in old_items:
        board.Remove(item)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix)
        )
    print(f"MOVED R610 to B.Cu 28.750,54.600 at 180 degrees")
    print(f"REMOVED old isolated +5V_RAW copper: {removed}")
    print(f"ADDED +5V_RAW via at {via_position}")
    print(f"ROUTED +5V_RAW {power_path}")
    print(
        f"ROUTED IR_LED_A2 {ir_path} -> In2.Cu "
        f"{ir_via_position}->{ir_end}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
