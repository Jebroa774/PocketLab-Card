"""Plan a track polyline that avoids all track keepouts on its copper layer."""

from __future__ import annotations

import argparse
import heapq
import math
from pathlib import Path

import pcbnew

from route_plane_fanouts import Rect, existing_obstacles, segment_intersects_rect, xy


def uuid_text(item: pcbnew.BOARD_ITEM) -> str:
    value = item.m_Uuid
    return value.AsString() if hasattr(value, "AsString") else str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--uuid", required=True)
    parser.add_argument("--step", type=float, default=0.20)
    parser.add_argument("--margin", type=float, default=0.10)
    parser.add_argument("--layer", choices=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))
    parser.add_argument(
        "--avoid-vias",
        type=float,
        default=0.0,
        metavar="RADIUS_MM",
        help="also treat every via as a square obstacle with this radius",
    )
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    matches = [item for item in board.GetTracks() if uuid_text(item) == args.uuid]
    if len(matches) != 1 or isinstance(matches[0], pcbnew.PCB_VIA):
        raise RuntimeError(f"expected one track UUID {args.uuid}, got {len(matches)}")
    track = matches[0]
    start, end = xy(track.GetStart()), xy(track.GetEnd())
    layer = board.GetLayerID(args.layer) if args.layer else track.GetLayer()
    rectangles = []
    for obstacle in existing_obstacles(board):
        if obstacle.kind == "keepout":
            rect, layers, disallow_tracks, _, _ = obstacle.geometry
            if disallow_tracks and layer in layers:
                rectangles.append(rect.expanded(args.margin))
        elif (
            obstacle.kind == "via"
            and args.avoid_vias > 0.0
            and obstacle.net != track.GetNetname()
        ):
            center, _ = obstacle.geometry
            rectangles.append(
                Rect(
                    center[0] - args.avoid_vias,
                    center[1] - args.avoid_vias,
                    center[0] + args.avoid_vias,
                    center[1] + args.avoid_vias,
                )
            )

    edge_box = board.GetBoardEdgesBoundingBox()
    left = pcbnew.ToMM(edge_box.GetLeft()) + args.margin
    top = pcbnew.ToMM(edge_box.GetTop()) + args.margin
    right = pcbnew.ToMM(edge_box.GetRight()) - args.margin
    bottom = pcbnew.ToMM(edge_box.GetBottom()) - args.margin

    def point(key: tuple[int, int]) -> tuple[float, float]:
        return start[0] + key[0] * args.step, start[1] + key[1] * args.step

    def inside_board(candidate: tuple[float, float]) -> bool:
        return left <= candidate[0] <= right and top <= candidate[1] <= bottom

    def clear(first: tuple[float, float], second: tuple[float, float]) -> bool:
        return inside_board(second) and not any(
            segment_intersects_rect(first, second, rect) for rect in rectangles
        )

    directions = (
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (1, -1), (-1, 1), (-1, -1),
    )
    origin = (0, 0)
    queue: list[tuple[float, float, tuple[int, int]]] = [
        (math.dist(start, end), 0.0, origin)
    ]
    cost = {origin: 0.0}
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    goal: tuple[int, int] | None = None
    while queue:
        _, current_cost, key = heapq.heappop(queue)
        if current_cost > cost.get(key, math.inf) + 1e-9:
            continue
        current = point(key)
        if math.dist(current, end) <= args.step * 1.5 and clear(current, end):
            goal = key
            break
        for dx, dy in directions:
            next_key = key[0] + dx, key[1] + dy
            candidate = point(next_key)
            if not clear(current, candidate):
                continue
            step_cost = args.step * (math.sqrt(2.0) if dx and dy else 1.0)
            next_cost = current_cost + step_cost
            if next_cost + 1e-9 >= cost.get(next_key, math.inf):
                continue
            cost[next_key] = next_cost
            previous[next_key] = key
            priority = next_cost + math.dist(candidate, end)
            heapq.heappush(queue, (priority, next_cost, next_key))
    if goal is None:
        raise RuntimeError("no keepout-clear route found")

    keys = [goal]
    while keys[-1] != origin:
        keys.append(previous[keys[-1]])
    keys.reverse()
    raw = [start, *(point(key) for key in keys[1:]), end]

    # Greedily remove grid points while preserving keepout clearance.
    simplified = [raw[0]]
    index = 0
    while index < len(raw) - 1:
        candidate_index = len(raw) - 1
        while candidate_index > index + 1 and not clear(raw[index], raw[candidate_index]):
            candidate_index -= 1
        simplified.append(raw[candidate_index])
        index = candidate_index

    print(
        f"TRACK net={track.GetNetname()} layer={board.GetLayerName(layer)} "
        f"start={start} end={end} points={len(simplified) - 2}"
    )
    for candidate in simplified[1:-1]:
        print(f"--point {candidate[0]:.4f},{candidate[1]:.4f}")
    print(f"LENGTH {sum(math.dist(a, b) for a, b in zip(simplified, simplified[1:])):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
