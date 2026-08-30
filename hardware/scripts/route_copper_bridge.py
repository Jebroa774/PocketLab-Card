"""Route one DRC-aware bridge between two existing copper islands."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

import route_lf_global as maze
from route_plane_fanouts import board_rect, existing_obstacles


def parse_point(value: str) -> tuple[float, float]:
    x_text, y_text = value.split(",", 1)
    return float(x_text), float(y_text)


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument("--start", type=parse_point, required=True)
    parser.add_argument("--end", type=parse_point, required=True)
    parser.add_argument(
        "--layer", choices=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"), default="B.Cu"
    )
    parser.add_argument(
        "--endpoint-vias",
        choices=("none", "F-B", "F-In1", "In1-B", "In1-In2", "In2-B"),
        default="none",
    )
    parser.add_argument("--via-diameter", type=float, default=0.30)
    parser.add_argument("--via-drill", type=float, default=0.10)
    parser.add_argument("--grid", type=float, default=0.20)
    parser.add_argument("--width", type=float, default=0.20)
    parser.add_argument("--clearance", type=float, default=0.20)
    parser.add_argument("--expansion", type=float, default=12.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    if output == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    net_name = args.net if args.net.startswith("/") else f"/{args.net}"
    if board.FindNet(net_name) is None:
        raise RuntimeError(f"Unknown net: {net_name}")
    layer = {
        "F.Cu": pcbnew.F_Cu,
        "In1.Cu": pcbnew.In1_Cu,
        "In2.Cu": pcbnew.In2_Cu,
        "B.Cu": pcbnew.B_Cu,
    }[args.layer]
    maze.GRID_MM = args.grid
    maze.TRACK_WIDTH_MM = args.width
    maze.DIFFERENT_NET_CLEARANCE_MM = args.clearance
    maze.AVOID_L3_ZONE_POLYS = ()
    maze.ROUTING_LAYERS = (layer,)
    # A bridge intentionally starts and ends on existing copper of its own
    # net.  The generic fixed-layer maze applies same-net spacing to vias and
    # tracks as well, which otherwise cages the search at an existing via or
    # track endpoint.  Unrelated copper remains fully obstacle-checked; the
    # final KiCad DRC still validates the completed candidate.
    obstacles = [
        obstacle
        for obstacle in existing_obstacles(board)
        if obstacle.net != net_name
    ]
    result = maze.find_fixed_layer_path_to_goals(
        net_name=net_name,
        start=args.start,
        ends=(args.end,),
        layer=layer,
        endpoint_pad_ids=set(),
        edge=board_rect(board),
        obstacles=obstacles,
        expansion=args.expansion,
    )
    if result is None:
        raise RuntimeError("No clear copper bridge path found")
    points, _ = result
    route = tuple((x, y, layer) for x, y in points)
    tracks, vias = maze.add_route(board, net_name, route, obstacles)
    via_pairs = {
        "F-B": (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.VIATYPE_THROUGH),
        "F-In1": (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.VIATYPE_MICROVIA),
        "In1-B": (pcbnew.In1_Cu, pcbnew.B_Cu, pcbnew.VIATYPE_BLIND),
        "In1-In2": (pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.VIATYPE_BURIED),
        "In2-B": (pcbnew.In2_Cu, pcbnew.B_Cu, pcbnew.VIATYPE_MICROVIA),
    }
    if args.endpoint_vias != "none":
        top, bottom, via_type = via_pairs[args.endpoint_vias]
        net = board.FindNet(net_name)
        assert net is not None
        for position in (args.start, args.end):
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(pcbnew.VECTOR2I_MM(*position))
            via.SetWidth(pcbnew.FromMM(args.via_diameter))
            via.SetDrill(pcbnew.FromMM(args.via_drill))
            via.SetViaType(via_type)
            via.SetLayerPair(top, bottom)
            via.SetNet(net)
            via.SetLocked(True)
            board.Add(via)
            vias += 1
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix))
    print(f"ROUTED {net_name}: tracks={tracks} vias={vias} points={len(points)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
