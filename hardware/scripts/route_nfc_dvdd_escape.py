"""Free the PN532 west escape and connect its split DVDD pins.

U2.3 originally reached the GND plane by running west and then south to the
shared U2.7 plane via.  That branch blocks the only manufacturable outer path
between the two DVDD lands U2.5/U2.8.  The exposed centre pad is GND, so U2.3
can instead terminate directly in it while DVDD uses the freed west corridor.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew


GND_BRANCH_SEGMENTS = (
    ((62.0625, 41.3500), (61.1000, 41.3500)),
    ((61.1000, 41.3500), (61.1000, 43.3500)),
    ((61.1000, 43.3500), (61.0625, 43.3500)),
)
SECONDARY_GND_BRANCH_SEGMENTS = (
    ((61.2500, 43.3500), (61.2500, 43.8500)),
    ((61.2500, 43.8500), (61.0000, 44.1000)),
)
OLD_MAIN_GND_VIA_MM = (61.0625, 43.3500)
NEW_MAIN_GND_VIA_MM = (61.2600, 43.2500)
MAIN_GND_JUNCTION_MM = (61.2600, 43.3500)
SECONDARY_GND_VIA_MM = (61.0000, 44.1000)


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
    width_mm: float = 0.15,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(*start))
    track.SetEnd(pcbnew.VECTOR2I_MM(*end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
            or item.GetNetname() != "/GND"
            or item.GetLayer() != pcbnew.F_Cu
        ):
            continue
        if any(
            same_segment(item, first, second)
            for first, second in GND_BRANCH_SEGMENTS + SECONDARY_GND_BRANCH_SEGMENTS
        ):
            removable.append(item)
    expected_removals = len(GND_BRANCH_SEGMENTS) + len(SECONDARY_GND_BRANCH_SEGMENTS)
    if len(removable) != expected_removals:
        raise RuntimeError(
            f"Expected {expected_removals} old west-side GND segments, "
            f"found {len(removable)}"
        )
    for item in removable:
        board.Remove(item)

    main_vias: list[pcbnew.PCB_VIA] = []
    secondary_vias: list[pcbnew.PCB_VIA] = []
    for item in board.Tracks():
        if not isinstance(item, pcbnew.PCB_VIA) or item.GetNetname() != "/GND":
            continue
        position = xy(item.GetPosition())
        if math.dist(position, OLD_MAIN_GND_VIA_MM) < 0.002:
            main_vias.append(item)
        if math.dist(position, SECONDARY_GND_VIA_MM) < 0.002:
            secondary_vias.append(item)
    if len(main_vias) != 1 or len(secondary_vias) != 1:
        raise RuntimeError(
            "Expected one main and one secondary west-side GND via; "
            f"found main={len(main_vias)}, secondary={len(secondary_vias)}"
        )
    board.Remove(secondary_vias[0])
    main_via = main_vias[0]
    main_via.SetPosition(pcbnew.VECTOR2I_MM(*NEW_MAIN_GND_VIA_MM))
    main_via.SetWidth(pcbnew.FromMM(0.45))
    main_via.SetDrill(pcbnew.FromMM(0.20))
    for item in board.Tracks():
        if isinstance(item, pcbnew.PCB_VIA) or item.GetNetname() != "/GND":
            continue
        replacement = (
            MAIN_GND_JUNCTION_MM
            if item.GetLayer() == pcbnew.F_Cu
            else NEW_MAIN_GND_VIA_MM
        )
        if math.dist(xy(item.GetStart()), OLD_MAIN_GND_VIA_MM) < 0.002:
            item.SetStart(pcbnew.VECTOR2I_MM(*replacement))
        if math.dist(xy(item.GetEnd()), OLD_MAIN_GND_VIA_MM) < 0.002:
            item.SetEnd(pcbnew.VECTOR2I_MM(*replacement))
    add_track(
        board,
        "/GND",
        MAIN_GND_JUNCTION_MM,
        NEW_MAIN_GND_VIA_MM,
        width_mm=0.20,
    )

    # U2.3 reaches the large exposed GND pad at x=62.95 mm.
    add_track(board, "/GND", (62.0625, 41.3500), (63.0000, 41.3500))

    # The 0.0875-mm centre-line window between LF_SCLK_5V and the former U2.3
    # branch is narrow but legal at x=60.70 mm: both sides retain 0.20 mm
    # copper clearance with the 0.15-mm DVDD track.
    dvdd_path = (
        (62.0625, 42.3500),
        (60.7000, 42.3500),
        (60.7000, 43.8500),
        (62.0625, 43.8500),
    )
    for start, end in zip(dvdd_path, dvdd_path[1:]):
        add_track(board, "/NFC_DVDD", start, end)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    print(
        f"Saved PN532 DVDD candidate: {output_path}; "
        f"removed_gnd={len(removable)}+1via; moved_gnd_via=1; "
        f"added_gnd=2; added_dvdd=3"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
