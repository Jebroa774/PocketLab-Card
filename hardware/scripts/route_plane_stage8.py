"""Close the reviewed dense GND/+3V3 fanouts and PN532 GND escapes.

The pass follows the split-5V stage.  It uses 0.45/0.20-mm tented vias and
0.15-mm outer-layer neckdowns only for low-current connections to the solid
L2 GND and the L3 +3V3 plane.  U2 pins 1 and 3 are routed explicitly because
the generic fanout search cannot safely leave the PN532's 0.50-mm pitch.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew

import route_plane_fanouts as fanout


GND = "/GND"


def point_of(item: pcbnew.BOARD_CONNECTED_ITEM, start: bool) -> tuple[float, float]:
    position = item.GetStart() if start else item.GetEnd()
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def remove_u17_orphan_ground_branch(board: pcbnew.BOARD) -> None:
    pairs = (
        ((40.9125, 54.2500), (41.6625, 53.5000)),
        ((41.6625, 53.5000), (41.9125, 53.5000)),
        ((41.9125, 53.5000), (42.1625, 53.2500)),
    )
    candidates: list[pcbnew.PCB_TRACK] = []
    for item in board.Tracks():
        if (
            isinstance(item, pcbnew.PCB_VIA)
            or item.GetNetname() != GND
            or item.GetLayer() != pcbnew.F_Cu
        ):
            continue
        start = point_of(item, True)
        end = point_of(item, False)
        if any(
            (math.dist(start, first) < 0.002 and math.dist(end, second) < 0.002)
            or (math.dist(start, second) < 0.002 and math.dist(end, first) < 0.002)
            for first, second in pairs
        ):
            candidates.append(item)
    orphan_vias = []
    for item in board.Tracks():
        if not isinstance(item, pcbnew.PCB_VIA) or item.GetNetname() != GND:
            continue
        position = item.GetPosition()
        if math.dist(
            (pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)),
            (42.1625, 53.2500),
        ) < 0.002:
            orphan_vias.append(item)
    if len(candidates) != len(pairs) or len(orphan_vias) != 1:
        raise RuntimeError(
            "Expected the three-track/one-via orphan GND branch at U17; "
            f"found tracks={len(candidates)}, vias={len(orphan_vias)}"
        )
    for item in (*candidates, *orphan_vias):
        board.Remove(item)


def add_track(
    board: pcbnew.BOARD,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(*start))
    track.SetEnd(pcbnew.VECTOR2I_MM(*end))
    track.SetWidth(pcbnew.FromMM(0.15))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(board.FindNet(GND))
    track.SetLocked(True)
    board.Add(track)


def route_u2_ground(board: pcbnew.BOARD) -> None:
    # Pin 1 reaches the exposed central GND pad directly.  Pin 3 uses the
    # narrow west-side channel to the pre-existing plane via at 61.0625/43.35.
    add_track(board, (62.0625, 40.3500), (63.0000, 40.5500))
    path = (
        (62.0625, 41.3500),
        (61.1000, 41.3500),
        (61.1000, 43.3500),
        (61.0625, 43.3500),
    )
    for start, end in zip(path, path[1:]):
        add_track(board, start, end)


def route(board: pcbnew.BOARD) -> tuple[int, int, int, list[str]]:
    # These are the reviewed manufacturing minima for this JLCPCB-targeted
    # revision.  Critical nets still retain their stricter custom rules.
    settings = board.GetDesignSettings()
    settings.m_TrackMinWidth = pcbnew.FromMM(0.15)
    settings.m_ViasMinSize = pcbnew.FromMM(0.45)
    settings.m_MinThroughDrill = pcbnew.FromMM(0.20)

    previous_targets = fanout.TARGET_NETS
    previous_manual = fanout.MANUAL_FANOUT_PADS
    previous_diameter = fanout.VIA_DIAMETER_MM
    previous_drill = fanout.VIA_DRILL_MM
    previous_clearance = fanout.DIFFERENT_NET_CLEARANCE_MM
    previous_radius = fanout.GRID_MAX_RADIUS_MM
    previous_distance = fanout.EXISTING_VIA_MAX_DISTANCE_MM
    try:
        fanout.TARGET_NETS = {GND: 0.15, "/+3V3": 0.15}
        fanout.MANUAL_FANOUT_PADS = frozenset({("U2", "1"), ("U2", "3")})
        fanout.VIA_DIAMETER_MM = 0.45
        fanout.VIA_DRILL_MM = 0.20
        fanout.DIFFERENT_NET_CLEARANCE_MM = 0.20
        fanout.GRID_MAX_RADIUS_MM = 12.0
        fanout.EXISTING_VIA_MAX_DISTANCE_MM = 15.0
        result = fanout.route(board)
    finally:
        fanout.TARGET_NETS = previous_targets
        fanout.MANUAL_FANOUT_PADS = previous_manual
        fanout.VIA_DIAMETER_MM = previous_diameter
        fanout.VIA_DRILL_MM = previous_drill
        fanout.DIFFERENT_NET_CLEARANCE_MM = previous_clearance
        fanout.GRID_MAX_RADIUS_MM = previous_radius
        fanout.EXISTING_VIA_MAX_DISTANCE_MM = previous_distance

    remove_u17_orphan_ground_branch(board)
    route_u2_ground(board)
    return result


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
    added, shared, grid, skipped = route(board)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    print(
        f"Saved dense-plane PCB: {output_path}; fanouts={added}; "
        f"shared={shared}; grid={grid}; skipped={len(skipped)}"
    )
    for entry in skipped:
        print(f"SKIPPED {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
