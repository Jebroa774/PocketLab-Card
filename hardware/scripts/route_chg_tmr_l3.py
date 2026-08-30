"""Route the trapped U5 timer pin to R114 through a reviewed L3 corridor."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

import route_lf_global as maze
import route_plane_fanouts as fanout
from move_r610_ir2 import find_footprint, find_pad, point, xy


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(0.20))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def add_microvia(
    board: pcbnew.BOARD, net_name: str, position: tuple[float, float]
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(*position))
    via.SetWidth(pcbnew.FromMM(0.30))
    via.SetDrill(pcbnew.FromMM(0.10))
    via.SetViaType(pcbnew.VIATYPE_MICROVIA)
    via.SetLayerPair(pcbnew.In2_Cu, pcbnew.B_Cu)
    via.SetNet(board.FindNet(net_name))
    via.SetLocked(True)
    board.Add(via)


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
    start_pad = find_pad(find_footprint(board, "U5"), "14")
    end_pad = find_pad(find_footprint(board, "R114"), "1")
    start = xy(start_pad.GetPosition())
    end_escape = (94.30, 56.60)
    endpoint_ids = {fanout.item_key(start_pad), fanout.item_key(end_pad)}
    obstacles = fanout.existing_obstacles(board)
    edge = fanout.board_rect(board)

    maze.TRACK_WIDTH_MM = 0.20
    maze.GRID_MM = 0.25
    maze.DIFFERENT_NET_CLEARANCE_MM = 0.20
    maze.MAX_ROUTE_SEARCH_STATES = 150_000
    result = maze.find_fixed_layer_path_to_goals(
        net_name="/CHG_TMR",
        start=start,
        ends=(end_escape,),
        layer=pcbnew.In2_Cu,
        endpoint_pad_ids=endpoint_ids,
        edge=edge,
        obstacles=obstacles,
        expansion=12.0,
    )
    if result is None:
        raise RuntimeError("No clearance-clean CHG_TMR L3 corridor found")
    route, _ = result
    add_microvia(board, "/CHG_TMR", start)
    for first, second in zip(route, route[1:]):
        add_track(board, "/CHG_TMR", pcbnew.In2_Cu, first, second)
    add_microvia(board, "/CHG_TMR", end_escape)
    add_track(
        board,
        "/CHG_TMR",
        pcbnew.B_Cu,
        end_escape,
        xy(end_pad.GetPosition()),
    )

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix)
        )
    print(f"ROUTED /CHG_TMR on In2.Cu: {route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
