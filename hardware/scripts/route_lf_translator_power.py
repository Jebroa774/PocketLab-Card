"""Connect U21 and C515 to the existing switched LF_5V distribution.

Run this after the seven LF/shared-SPI global nets and before plane fanouts.
The HTRC110 supply trunk remains 0.50 mm.  U21 is a low-current logic load,
so its board-spanning branch is 0.30 mm; only the TSSOP VCC escape uses the
reviewed 0.39-mm neck before widening locally to 0.50 mm at C515.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

import route_lf_global as router


NET = "/LF_5V"
NECK_WIDTH_MM = 0.39
LOCAL_WIDTH_MM = 0.50
BRANCH_WIDTH_MM = 0.30
# Keep the TSSOP neck narrow until it has cleared adjacent U21.13 (GND), then
# let the local branch widen to 0.50 mm on its way to the decoupler.
SEED = (78.0125, 31.75)


def add_track(
    board: pcbnew.BOARD,
    obstacles: list[router.CopperObstacle],
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(router.point(*start))
    track.SetEnd(router.point(*end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(router.F)
    track.SetNet(board.FindNet(NET))
    track.SetLocked(True)
    board.Add(track)
    obstacles.append(
        router.CopperObstacle(
            NET, "track", (start, end, width_mm / 2.0, router.F), track
        )
    )


def route_connection(
    board: pcbnew.BOARD,
    obstacles: list[router.CopperObstacle],
    edge: router.Rect,
    start_pad: pcbnew.PAD,
    end_pad: pcbnew.PAD,
    width_mm: float,
    via_diameter_mm: float,
    start_override: tuple[float, float] | None = None,
) -> tuple[int, int]:
    router.TRACK_WIDTH_MM = width_mm
    router.VIA_DIAMETER_MM = via_diameter_mm
    route = router.find_route(
        net_name=NET,
        start_pad=start_pad,
        end_pad=end_pad,
        edge=edge,
        obstacles=obstacles,
        start_override=start_override,
    )
    if route is None:
        raise RuntimeError(
            f"No LF_5V route from {start_pad.GetParentFootprint().GetReference()} "
            f"to {end_pad.GetParentFootprint().GetReference()}"
        )
    return router.add_route(board, NET, route, obstacles)


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
    edge = router.board_rect(board)
    obstacles = router.existing_obstacles(board)
    u21_vcc = router.pad_by_reference(board, "U21", "14")
    c515_vcc = router.pad_by_reference(board, "C515", "1")
    c502_vcc = router.pad_by_reference(board, "C502", "1")
    if any(pad.GetNetname() != NET for pad in (u21_vcc, c515_vcc, c502_vcc)):
        raise RuntimeError("LF translator power endpoint net mismatch")

    total_tracks = 0
    total_vias = 0
    if not router.already_connected(board, u21_vcc, c515_vcc):
        start = router.xy(u21_vcc.GetPosition())
        source_pads = {router.item_key(u21_vcc)}
        if not router.track_segment_is_clear(
            net_name=NET,
            layer=router.F,
            start=start,
            end=SEED,
            width_mm=NECK_WIDTH_MM,
            source_pads=source_pads,
            edge=edge,
            obstacles=obstacles,
        ):
            raise RuntimeError("Reviewed U21 LF_5V neckdown is blocked")
        add_track(board, obstacles, start, SEED, NECK_WIDTH_MM)
        total_tracks += 1
        tracks, vias = route_connection(
            board,
            obstacles,
            edge,
            u21_vcc,
            c515_vcc,
            LOCAL_WIDTH_MM,
            0.70,
            start_override=SEED,
        )
        total_tracks += tracks
        total_vias += vias

    if not router.already_connected(board, c515_vcc, c502_vcc):
        tracks, vias = route_connection(
            board,
            obstacles,
            edge,
            c515_vcc,
            c502_vcc,
            BRANCH_WIDTH_MM,
            0.50,
        )
        total_tracks += tracks
        total_vias += vias

    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    endpoints = (
        router.pad_by_reference(reloaded, "U21", "14"),
        router.pad_by_reference(reloaded, "C515", "1"),
        router.pad_by_reference(reloaded, "C502", "1"),
    )
    if not router.already_connected(reloaded, endpoints[0], endpoints[1]):
        raise RuntimeError("Serialized PCB lost the U21-to-C515 LF_5V route")
    if not router.already_connected(reloaded, endpoints[1], endpoints[2]):
        raise RuntimeError("Serialized PCB lost the translator LF_5V trunk")
    print(
        f"Saved LF translator power: {output_path}; "
        f"segments={total_tracks}; vias={total_vias}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
