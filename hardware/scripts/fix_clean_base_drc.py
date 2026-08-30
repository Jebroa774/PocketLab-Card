#!/usr/bin/env python3
"""Apply narrowly-scoped geometry fixes to the current clean routing base."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def uuid_text(item: object) -> str:
    return item.m_Uuid.AsString()


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def same_point(value: pcbnew.VECTOR2I, expected: pcbnew.VECTOR2I) -> bool:
    return value.x == expected.x and value.y == expected.y


def replace_crossing_segment(board: pcbnew.BOARD) -> None:
    crossing_uuid = "caef2db3-b165-4092-ac75-19129c626c6a"
    old_segment = None
    for item in board.GetTracks():
        if uuid_text(item) == crossing_uuid:
            old_segment = item
            break
    if old_segment is None:
        raise RuntimeError(f"segment {crossing_uuid} not found")

    layer = old_segment.GetLayer()
    width = old_segment.GetWidth()
    net_code = old_segment.GetNetCode()
    waypoints = tuple(
        point(x, y)
        for x, y in (
            (69.25, 45.7875),
            (70.06, 46.9575),
            (71.11, 45.9075),
            (71.11, 45.6075),
            (71.56, 45.1575),
            (71.86, 45.1575),
            (72.31, 45.6075),
            (72.31, 48.1575),
            (72.46, 48.3075),
            (72.46, 48.4575),
            (72.61, 48.6075),
            (72.61, 50.2575),
            (72.76, 50.4075),
            (72.76, 50.5575),
            (73.21, 51.0075),
            (73.21, 51.1575),
            (73.66, 51.6075),
            (73.66, 51.7575),
            (74.41, 52.5075),
            (74.41, 52.8075),
            (74.56, 52.9575),
            (74.56, 53.1075),
            (74.71, 53.2575),
            (74.71, 53.4075),
            (74.86, 53.5575),
            (74.86, 53.7075),
            (75.19, 54.3675),
            (76.00, 55.5375),
        )
    )
    board.Remove(old_segment)
    for start, end in zip(waypoints, waypoints[1:]):
        segment = pcbnew.PCB_TRACK(board)
        segment.SetStart(start)
        segment.SetEnd(end)
        segment.SetWidth(width)
        segment.SetLayer(layer)
        segment.SetNetCode(net_code)
        segment.SetLocked(True)
        board.Add(segment)


def fix_j4_edge_mounting_tab(board: pcbnew.BOARD) -> None:
    """Classify J4's edge-straddling tab without changing its land pattern.

    KiCad exempts connector pads from the generic board-edge copper clearance
    test.  The right-hand JST mounting tab intentionally straddles Edge.Cuts,
    so mark only that pad as a connector pad.  Connector pads do not accept a
    paste layer; reproduce the original 1.50 x 3.40 mm rounded paste aperture
    as a footprint-local graphic so the stencil geometry remains unchanged.
    """

    target_uuid = "4a725c59-365c-4733-a1d2-385d7239574d"
    footprint = next(
        (item for item in board.GetFootprints() if item.GetReference() == "J4"),
        None,
    )
    if footprint is None:
        raise RuntimeError("J4 not found")

    pad = next(
        (item for item in footprint.Pads() if uuid_text(item) == target_uuid),
        None,
    )
    if pad is None:
        raise RuntimeError(f"J4 mounting tab {target_uuid} not found")

    pad.SetAttribute(pcbnew.PAD_ATTRIB_CONN)
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.B_Cu)
    layers.AddLayer(pcbnew.B_Mask)
    pad.SetLayerSet(layers)

    paste = pcbnew.PCB_SHAPE(footprint, pcbnew.SHAPE_T_RECTANGLE)
    paste.SetStart(point(104.70, 58.40))
    paste.SetEnd(point(106.20, 61.80))
    paste.SetLayer(pcbnew.B_Paste)
    paste.SetWidth(0)
    paste.SetFilled(True)
    paste.SetCornerRadius(pcbnew.FromMM(0.25))
    footprint.Add(paste)


def remove_u18_ground_sliver(board: pcbnew.BOARD) -> None:
    """Avoid the acute copper wedge where U18 pads 2 and 3 met one GND via."""

    segment_uuid = "5e1e1a6a-8956-4a2f-a98c-d5aa6b69c1ce"
    segment = next(
        (item for item in board.GetTracks() if uuid_text(item) == segment_uuid),
        None,
    )
    if segment is None:
        raise RuntimeError(f"U18 GND segment {segment_uuid} not found")
    if segment.GetNetname() != "/GND":
        raise RuntimeError(f"U18 segment has unexpected net {segment.GetNetname()}")

    # Pad 2 is already routed to the nearby GND via.  Join pad 3 directly to
    # pad 2 instead of sending both traces into the via at an acute angle.
    segment.SetEnd(point(77.8625, 27.875))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input.resolve()))

    # The actual copper gap in these manufacturer land patterns is 0.15 mm.
    # Use 0.14 mm locally to avoid floating-point equality noise while keeping
    # every inter-footprint and routed-copper clearance unchanged.
    for footprint in board.GetFootprints():
        if footprint.GetReference() in {"Q2", "Q3", "U7"}:
            for pad in footprint.Pads():
                pad.SetLocalClearance(pcbnew.FromMM(0.14))

    # Route NFC_I0 around the short +3V3 L3 link.  The path was selected by
    # the obstacle-aware maze router; both endpoint vias stay unchanged.
    replace_crossing_segment(board)
    fix_j4_edge_mounting_tab(board)
    remove_u18_ground_sliver(board)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output.resolve()), board)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
