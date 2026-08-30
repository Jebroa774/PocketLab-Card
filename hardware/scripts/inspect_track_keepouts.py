"""Report rule-area keepouts intersected by selected PCB tracks."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

from route_plane_fanouts import existing_obstacles, segment_intersects_rect, xy


def uuid_text(item: pcbnew.BOARD_ITEM) -> str:
    value = item.m_Uuid
    return value.AsString() if hasattr(value, "AsString") else str(value)


def owner_text(zone: pcbnew.ZONE) -> str:
    parent = zone.GetParent()
    if isinstance(parent, pcbnew.FOOTPRINT):
        return parent.GetReference()
    return "BOARD"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--uuid", action="append", required=True)
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    by_uuid = {uuid_text(item): item for item in board.GetTracks()}
    keepouts = [entry for entry in existing_obstacles(board) if entry.kind == "keepout"]
    for item_uuid in args.uuid:
        item = by_uuid.get(item_uuid)
        if item is None:
            print(f"MISSING {item_uuid}")
            continue
        start, end = xy(item.GetStart()), xy(item.GetEnd())
        layer = item.GetLayer()
        print(
            f"TRACK {item_uuid} net={item.GetNetname()} "
            f"layer={board.GetLayerName(layer)} start={start} end={end}"
        )
        hits = 0
        for obstacle in keepouts:
            rect, layers, no_tracks, _, _ = obstacle.geometry
            if not no_tracks or layer not in layers:
                continue
            if not segment_intersects_rect(start, end, rect):
                continue
            hits += 1
            print(
                f"  HIT owner={owner_text(obstacle.owner)} "
                f"rect=({rect.left:.3f},{rect.top:.3f})-"
                f"({rect.right:.3f},{rect.bottom:.3f})"
            )
        print(f"  hits={hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
