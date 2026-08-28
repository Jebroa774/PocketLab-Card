#!/usr/bin/env python3
"""Locate KiCad copper-sliver marker coordinates from board geometry.

This mirrors KiCad's DRC_TEST_PROVIDER_SLIVER_CHECKER closely enough to expose
the marker position that the CLI JSON report currently omits.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew


def items_on_layer(board: pcbnew.BOARD, layer: int):
    for item in board.GetTracks():
        if item.IsOnLayer(layer):
            yield item

    for item in board.GetDrawings():
        if item.IsOnLayer(layer):
            yield item

    for footprint in board.GetFootprints():
        for field in footprint.GetFields():
            if field.IsOnLayer(layer):
                yield field

        for pad in footprint.Pads():
            if pad.HasHole() or pad.IsOnLayer(layer):
                yield pad

        for item in footprint.GraphicalItems():
            if item.IsOnLayer(layer):
                yield item

        for zone in footprint.Zones():
            if zone.IsOnLayer(layer):
                yield zone


def combined_copper(board: pcbnew.BOARD, layer: int) -> pcbnew.SHAPE_POLY_SET:
    poly = pcbnew.SHAPE_POLY_SET()

    for zone in board.Zones():
        if zone.GetIsRuleArea() or not zone.IsOnLayer(layer):
            continue
        fill = zone.GetFill(layer)
        if fill is not None:
            poly.Append(fill)

    approximation_error = pcbnew.FromMM(pcbnew.ARC_LOW_DEF_MM)
    for item in items_on_layer(board, layer):
        if isinstance(item, pcbnew.ZONE):
            if item.GetIsRuleArea():
                continue
            fill = item.GetFill(layer)
            if fill is not None:
                poly.Append(fill)
        else:
            item.TransformShapeToPolygon(
                poly,
                layer,
                0,
                approximation_error,
                pcbnew.ERROR_INSIDE,
            )

    poly.Simplify()
    return poly


def area(p, q, r) -> int:
    return (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)


def find_slivers(poly: pcbnew.SHAPE_POLY_SET):
    width_tolerance = pcbnew.FromMM(0.08)
    squared_width = width_tolerance * width_tolerance
    min_len = pcbnew.FromMM(0.0008)
    cosangle_tolerance = 2.0 * math.cos(math.radians(20.0))

    for outline_index in range(poly.OutlineCount()):
        pts = list(poly.Outline(outline_index).CPoints())
        pt_count = len(pts)
        if pt_count <= 5:
            continue

        def locally_inside(index_a: int, index_b: int) -> bool:
            previous = (pt_count + index_a - 1) % pt_count
            following = (index_a + 1) % pt_count
            if area(pts[previous], pts[index_a], pts[following]) < 0:
                return (
                    area(pts[index_a], pts[index_b], pts[following]) >= 0
                    and area(pts[index_a], pts[previous], pts[index_b]) >= 0
                )
            return (
                area(pts[index_a], pts[index_b], pts[previous]) < 0
                or area(pts[index_a], pts[following], pts[index_b]) < 0
            )

        index = 0
        offset = 1
        while index < pt_count:
            prior_index = (pt_count + index - 1) % pt_count
            next_index = (index + 1) % pt_count
            point = pts[index]
            point_prior = pts[prior_index]
            prior_x = point_prior.x - point.x
            prior_y = point_prior.y - point.y
            forward_offset = 1
            offset = 1

            while abs(prior_x) < min_len and abs(prior_y) < min_len and offset < pt_count:
                point = pts[(index + offset) % pt_count]
                offset += 1
                prior_x = point_prior.x - point.x
                prior_y = point_prior.y - point.y

            if offset >= pt_count:
                break

            point_after = pts[next_index]
            after_x = point_after.x - point.x
            after_y = point_after.y - point.y

            while (
                abs(after_x) < min_len
                and abs(after_y) < min_len
                and forward_offset < pt_count
            ):
                next_index = (index + forward_offset) % pt_count
                forward_offset += 1
                point_after = pts[next_index]
                after_x = point_after.x - point.x
                after_y = point_after.y - point.y

            if offset >= pt_count:
                break

            if prior_x * after_x + prior_y * after_y > 0 and locally_inside(prior_index, next_index):
                included_x = point_after.x - point_prior.x
                included_y = point_after.y - point_prior.y
                arm1 = prior_x * prior_x + prior_y * prior_y
                arm2 = after_x * after_x + after_y * after_y
                opposite = included_x * included_x + included_y * included_y
                cos_angle = abs((opposite - arm1 - arm2) / math.sqrt(arm1 * arm2))
                if (
                    cos_angle > cosangle_tolerance
                    and 2.0 - cos_angle > 1.1920929e-7
                    and opposite > squared_width
                ):
                    yield point

            index += offset


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("board", type=Path)
    parser.add_argument("--layer", default="B.Cu")
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.board.resolve()))
    layer = board.GetLayerID(args.layer)
    poly = combined_copper(board, layer)
    for point in find_slivers(poly):
        print(
            f"{args.layer}: {point.x}|{point.y} "
            f"({pcbnew.ToMM(point.x):.6f}, {pcbnew.ToMM(point.y):.6f}) mm"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
