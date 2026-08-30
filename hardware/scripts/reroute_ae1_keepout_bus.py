"""Reroute direct candidate tracks around the AE1 all-copper keepout.

The fast connectivity pass drew several top-row signals straight through the
NFC antenna rule areas.  This candidate-only repair fans them into ordered
lanes above AE1 and down ordered corridors to its right.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


F = pcbnew.F_Cu
I1 = pcbnew.In1_Cu
I2 = pcbnew.In2_Cu
B = pcbnew.B_Cu

# UUID, target layer, top-lane Y, right-corridor X.  Entries on each layer are
# ordered by their top-row X coordinate, preventing bus self-crossings.
ROUTES = (
    # In1.Cu
    ("a1322ea6-3173-4b81-85d9-cb98374b1672", I1, 23.20, 59.20),
    ("ee80aeb4-f206-4c14-b61f-5d5de15e1df1", I1, 22.80, 59.60),
    ("68d051f8-cbf0-45d7-a895-97e092ea5cc1", I1, 22.40, 60.00),
    ("043380f4-dd3e-4277-be28-9635f68354f5", I1, 21.25, 60.40),
    ("02dfc033-b619-47f3-a820-3abd3a0f0940", I1, 20.75, 60.80),
    # In2.Cu
    ("fab03f7e-3496-4bd1-bc67-779da9e6c1aa", I2, 23.20, 59.20),
    ("a5680891-3988-448e-93b9-8e61f552c99b", I2, 22.80, 59.60),
    ("b6529aa1-70ee-40cf-85c4-e55717eaaaf7", I2, 22.40, 60.00),
    ("d903afd7-6ba2-4509-b97e-3fe8482ee8f3", I2, 21.25, 60.40),
    ("5523d42c-d717-4ab8-beb5-efb4e0dfa6b5", I2, 20.75, 60.80),
    # B.Cu
    ("1576ca56-b3c8-4f92-a1b3-ec5ef71672c8", B, 23.20, 59.20),
    ("60451108-30f1-4b8b-aab2-95e54d32efef", B, 22.80, 59.60),
    ("c1cf036c-7ee6-49a7-aa95-06d9f36329de", B, 22.40, 60.00),
    ("531e5672-687c-44cc-9008-cca512a0c9ec", B, 21.25, 60.40),
    # F.Cu: one isolated lane below the top-row SMD lands.
    ("dee4947d-f21f-4cd5-900a-f574add3b939", F, 23.20, 59.20),
)

BOTTOM_Y = 52.80
KEEPOUT_RIGHT_X = 58.90


def uuid_text(item: pcbnew.BOARD_ITEM) -> str:
    value = item.m_Uuid
    return value.AsString() if hasattr(value, "AsString") else str(value)


def mm_point(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def vector(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(*position)


def endpoint_is_anchored(
    board: pcbnew.BOARD,
    position: pcbnew.VECTOR2I,
    net_code: int,
    layer: int,
) -> bool:
    tolerance = pcbnew.FromMM(0.002)

    def coincident(first: pcbnew.VECTOR2I, second: pcbnew.VECTOR2I) -> bool:
        return (first - second).EuclideanNorm() <= tolerance

    for item in board.GetTracks():
        if item.GetNetCode() != net_code:
            continue
        if isinstance(item, pcbnew.PCB_VIA):
            if coincident(item.GetPosition(), position) and item.IsOnLayer(layer):
                return True
        elif item.GetLayer() == layer and (
            coincident(item.GetStart(), position) or coincident(item.GetEnd(), position)
        ):
            return True
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if (
                pad.GetNetCode() == net_code
                and coincident(pad.GetPosition(), position)
                and layer in set(pad.GetLayerSet().Seq())
            ):
                return True
    return False


def compact(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result: list[tuple[float, float]] = []
    for entry in points:
        if not result or entry != result[-1]:
            result.append(entry)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    hardware_dir = Path(__file__).resolve().parent.parent
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if args.output.resolve() in {authoritative, args.input.resolve()}:
        raise RuntimeError("output must be a separate non-authoritative board")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    by_uuid = {uuid_text(item): item for item in board.GetTracks()}
    selected: list[tuple[pcbnew.PCB_TRACK, int, float, float]] = []
    for item_uuid, layer, lane_y, corridor_x in ROUTES:
        item = by_uuid.get(item_uuid)
        if item is None or isinstance(item, pcbnew.PCB_VIA):
            raise RuntimeError(f"missing track UUID: {item_uuid}")
        selected.append((item, layer, lane_y, corridor_x))

    added = 0
    for original, layer, lane_y, corridor_x in selected:
        first_position = original.GetStart()
        second_position = original.GetEnd()
        first = mm_point(first_position)
        second = mm_point(second_position)
        if first[1] <= second[1]:
            top_position, other_position = first_position, second_position
            top, other = first, second
        else:
            top_position, other_position = second_position, first_position
            top, other = second, first
        net = original.GetNet()
        net_code = original.GetNetCode()
        width = original.GetWidth()
        locked = original.IsLocked()
        board.Remove(original)
        if not endpoint_is_anchored(board, top_position, net_code, layer):
            raise RuntimeError(f"top endpoint is not anchored: {original.GetNetname()}")
        if not endpoint_is_anchored(board, other_position, net_code, layer):
            raise RuntimeError(f"far endpoint is not anchored: {original.GetNetname()}")

        points = [top, (top[0], lane_y), (corridor_x, lane_y)]
        if other[0] < KEEPOUT_RIGHT_X and other[1] > BOTTOM_Y:
            points.extend(((corridor_x, BOTTOM_Y), other))
        else:
            points.append(other)
        points = compact(points)
        for start, end in zip(points, points[1:]):
            segment = pcbnew.PCB_TRACK(board)
            segment.SetStart(vector(start))
            segment.SetEnd(vector(end))
            segment.SetLayer(layer)
            segment.SetWidth(width)
            segment.SetNet(net)
            segment.SetLocked(locked)
            board.Add(segment)
            added += 1

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    opens = int(connectivity.GetUnconnectedCount(False))
    if opens:
        raise RuntimeError(f"AE1 bus created {opens} open connection(s)")

    pcbnew.SaveBoard(str(args.output.resolve()), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix)
        )
    print(f"AE1_BUS routes={len(selected)} segments={added} opens={opens}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
