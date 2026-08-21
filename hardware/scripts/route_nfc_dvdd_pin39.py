"""PN532 north-west corridor route for DVDD pin 39.

The existing LF_SCLK_5V trace crosses immediately above U2.39.  Move only
that local section to In1.Cu, then use the released F.Cu corridor to connect
U2.39 to the already-routed U2.5/U2.8 DVDD island.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew


OLD_CLOCK_PATH = (
    ((66.037499, 36.800000), (65.787499, 37.050000)),
    ((65.787499, 37.050000), (64.037499, 37.050000)),
    ((64.037499, 37.050000), (64.037499, 38.050000)),
    ((64.037499, 38.050000), (63.287499, 38.800000)),
    ((63.287499, 38.800000), (62.287499, 38.800000)),
    ((62.287499, 38.800000), (60.700000, 39.700000)),
    ((60.700000, 39.700000), (60.287499, 40.800000)),
    ((60.287499, 40.800000), (59.740000, 41.200000)),
    ((59.740000, 41.200000), (59.740000, 42.500000)),
    ((59.740000, 42.500000), (60.287499, 42.900000)),
    ((60.287499, 42.900000), (60.287499, 52.300000)),
)

CLOCK_VIAS = ((66.037499, 36.800000),)
CLOCK_IN1_PATH = (
    (66.037499, 36.800000),
    (65.300000, 36.200000),
    (59.050000, 36.200000),
    (59.050000, 51.700000),
    (59.550000, 52.200000),
    (60.287499, 52.300000),
)

DVDD_PATH = (
    (63.250000, 39.662500),
    (63.250000, 39.100000),
    (61.100000, 39.100000),
    (61.100000, 42.350000),
    (62.062500, 42.350000),
)


def xy(vector: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vector.x), pcbnew.ToMM(vector.y)


def same_segment(
    item: pcbnew.PCB_TRACK,
    first: tuple[float, float],
    second: tuple[float, float],
) -> bool:
    start = xy(item.GetStart())
    end = xy(item.GetEnd())
    return (
        math.dist(start, first) < 0.002 and math.dist(end, second) < 0.002
    ) or (
        math.dist(start, second) < 0.002 and math.dist(end, first) < 0.002
    )


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: int,
    width_mm: float,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(*start))
    track.SetEnd(pcbnew.VECTOR2I_MM(*end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(layer)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def add_via(
    board: pcbnew.BOARD, net_name: str, position: tuple[float, float]
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pcbnew.VECTOR2I_MM(*position))
    via.SetWidth(pcbnew.FromMM(0.30))
    via.SetDrill(pcbnew.FromMM(0.10))
    via.SetViaType(pcbnew.VIATYPE_MICROVIA)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.In1_Cu)
    via.SetNet(board.FindNet(net_name))
    via.SetLocked(True)
    board.Add(via)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--clock-only",
        action="store_true",
        help="Only free the F.Cu corridor; leave DVDD routing to another pass",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    main_board = Path(__file__).resolve().parent.parent / "PocketLab-Card.kicad_pcb"
    if output_path == main_board.resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    removable: list[pcbnew.PCB_TRACK] = []
    for item in board.Tracks():
        if (
            isinstance(item, pcbnew.PCB_VIA)
            or item.GetNetname() != "/LF_SCLK_5V"
            or item.GetLayer() != pcbnew.F_Cu
        ):
            continue
        if any(same_segment(item, first, second) for first, second in OLD_CLOCK_PATH):
            removable.append(item)
    if len(removable) != len(OLD_CLOCK_PATH):
        raise RuntimeError(
            f"Expected {len(OLD_CLOCK_PATH)} local LF_SCLK_5V segments, "
            f"found {len(removable)}"
        )
    for item in removable:
        board.Remove(item)

    for position in CLOCK_VIAS:
        add_via(board, "/LF_SCLK_5V", position)
    for start, end in zip(CLOCK_IN1_PATH, CLOCK_IN1_PATH[1:]):
        add_track(board, "/LF_SCLK_5V", start, end, pcbnew.In1_Cu, 0.15)
    if not args.clock_only:
        for start, end in zip(DVDD_PATH, DVDD_PATH[1:]):
            add_track(board, "/NFC_DVDD", start, end, pcbnew.F_Cu, 0.15)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    connectivity = reloaded.GetConnectivity()
    connectivity.RecalculateRatsnest()
    u2 = reloaded.FindFootprintByReference("U2")
    if u2 is None:
        raise RuntimeError("U2 missing after save/reload")
    pads = {pad.GetNumber(): pad for pad in u2.Pads()}
    connected_to_39 = {
        item.m_Uuid.AsString() for item in connectivity.GetConnectedItems(pads["39"])
    }
    if not args.clock_only and pads["5"].m_Uuid.AsString() not in connected_to_39:
        raise RuntimeError("U2.39 did not connect to U2.5 after save/reload")
    print(
        f"Saved PN532 DVDD pin-39 candidate: {output_path}; "
        f"removed_clock={len(removable)}; added_clock=5+1microvia; "
        f"added_dvdd={0 if args.clock_only else len(DVDD_PATH) - 1}; "
        f"unconnected={int(connectivity.GetUnconnectedCount(False))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
