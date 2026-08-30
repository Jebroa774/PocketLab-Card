"""Find short legal F.Cu microvia bridges across an In1 signal cut."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew

from autoroute_in1_candidate import mm, segment_clear_on_layer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--cutter-net", required=True)
    parser.add_argument("--plane-net", default="/GND")
    parser.add_argument("--sample-step", type=float, default=0.40)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    zone = next(
        zone
        for zone in board.Zones()
        if zone.GetNetname() == args.plane_net
        and zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    )
    polygons = zone.GetFilledPolysList(pcbnew.In1_Cu)
    found = []
    offsets = (0.55, 0.65, 0.75, 0.90, 1.10, 1.30, 1.50, 1.80, 2.10)
    for track in board.GetTracks():
        if (
            track.Type() != pcbnew.PCB_TRACE_T
            or track.GetNetname() != args.cutter_net
            or track.GetLayer() != pcbnew.In1_Cu
        ):
            continue
        start = mm(track.GetStart().x), mm(track.GetStart().y)
        end = mm(track.GetEnd().x), mm(track.GetEnd().y)
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 0.50:
            continue
        normal = -dy / length, dx / length
        samples = max(1, int(length / args.sample_step))
        for index in range(samples + 1):
            fraction = index / samples
            center = start[0] + fraction * dx, start[1] + fraction * dy
            for offset in offsets:
                left = center[0] - normal[0] * offset, center[1] - normal[1] * offset
                right = center[0] + normal[0] * offset, center[1] + normal[1] * offset
                if not (
                    polygons.Collide(pcbnew.VECTOR2I_MM(*left))
                    and polygons.Collide(pcbnew.VECTOR2I_MM(*right))
                ):
                    continue
                if any(
                    not segment_clear_on_layer(
                        board, layer, args.plane_net, left, left, item_radius=0.15
                    )
                    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu)
                ):
                    continue
                if any(
                    not segment_clear_on_layer(
                        board, layer, args.plane_net, right, right, item_radius=0.15
                    )
                    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu)
                ):
                    continue
                if not segment_clear_on_layer(
                    board, pcbnew.F_Cu, args.plane_net, left, right
                ):
                    continue
                found.append((math.dist(left, right), left, right))

    unique = sorted(
        {
            (
                round(length, 6),
                (round(left[0], 6), round(left[1], 6)),
                (round(right[0], 6), round(right[1], 6)),
            )
            for length, left, right in found
        }
    )
    for length, left, right in unique[: args.limit]:
        print(
            f"{length:.3f} {left[0]:.3f},{left[1]:.3f} -> "
            f"{right[0]:.3f},{right[1]:.3f}"
        )
    print(f"FOUND {len(unique)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
