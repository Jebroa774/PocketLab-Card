"""Rank newly added candidate copper by its participation in KiCad DRC errors."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

import pcbnew


ROUTING_TYPES = {
    "clearance",
    "hole_clearance",
    "shorting_items",
    "tracks_crossing",
    "hole_to_hole",
    "items_not_allowed",
    "copper_edge_clearance",
    "track_dangling",
}


def geometry_key(item: pcbnew.BOARD_ITEM) -> tuple:
    if isinstance(item, pcbnew.PCB_VIA):
        return (
            "via",
            item.GetPosition().x,
            item.GetPosition().y,
            item.GetWidth(pcbnew.F_Cu),
            item.GetDrillValue(),
            int(item.GetViaType()),
            item.TopLayer(),
            item.BottomLayer(),
            item.GetNetname(),
        )
    first = (item.GetStart().x, item.GetStart().y)
    second = (item.GetEnd().x, item.GetEnd().y)
    if second < first:
        first, second = second, first
    return (
        "track",
        first,
        second,
        item.GetWidth(),
        item.GetLayer(),
        item.GetNetname(),
    )


def uuid_text(item: pcbnew.BOARD_ITEM) -> str:
    value = item.m_Uuid
    return value.AsString() if hasattr(value, "AsString") else str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--top", type=int, default=80)
    args = parser.parse_args()

    base = pcbnew.LoadBoard(str(args.base.resolve()))
    candidate = pcbnew.LoadBoard(str(args.candidate.resolve()))
    base_keys = {geometry_key(item) for item in base.GetTracks()}
    copper_by_uuid = {uuid_text(item): item for item in candidate.GetTracks()}
    new_by_uuid = {
        item_uuid: item
        for item_uuid, item in copper_by_uuid.items()
        if geometry_key(item) not in base_keys
    }

    report = json.loads(args.drc.read_text(encoding="utf-8"))
    score = Counter()
    type_score: dict[str, Counter] = defaultdict(Counter)
    violation_counts = Counter()
    ownership = Counter()
    violations_with_new = 0

    for violation in report.get("violations", []):
        violation_type = violation.get("type", "unknown")
        violation_counts[violation_type] += 1
        uuids = [entry.get("uuid", "") for entry in violation.get("items", [])]
        new_uuids = {item_uuid for item_uuid in uuids if item_uuid in new_by_uuid}
        old_copper = {item_uuid for item_uuid in uuids if item_uuid in copper_by_uuid and item_uuid not in new_by_uuid}
        if new_uuids:
            violations_with_new += 1
            ownership["with_new"] += 1
            if old_copper:
                ownership["new_and_old_copper"] += 1
            if len(new_uuids) == len(set(uuids)):
                ownership["only_new_items"] += 1
        else:
            ownership["without_new"] += 1
        if violation_type not in ROUTING_TYPES:
            continue
        for item_uuid in new_uuids:
            score[item_uuid] += 1
            type_score[item_uuid][violation_type] += 1

    print(
        f"COPPER base={len(base_keys)} candidate={len(copper_by_uuid)} "
        f"new={len(new_by_uuid)}"
    )
    print(
        f"VIOLATIONS total={sum(violation_counts.values())} "
        f"with_new={violations_with_new} without_new={ownership['without_new']}"
    )
    print("OWNERSHIP " + " ".join(f"{key}={value}" for key, value in ownership.most_common()))
    print("TYPES " + " ".join(f"{key}={value}" for key, value in violation_counts.most_common()))
    print("SCORE_BUCKETS")
    for threshold in (20, 10, 8, 6, 5, 4, 3, 2, 1):
        print(f"  >= {threshold}: {sum(value >= threshold for value in score.values())}")
    print("TOP_NEW_COPPER")
    for item_uuid, value in score.most_common(args.top):
        item = new_by_uuid[item_uuid]
        position = item.GetPosition() if isinstance(item, pcbnew.PCB_VIA) else item.GetStart()
        kind = "via" if isinstance(item, pcbnew.PCB_VIA) else "track"
        details = ",".join(f"{key}:{count}" for key, count in type_score[item_uuid].most_common())
        print(
            f"  {value:3d} {kind:5s} {item.GetNetname():24s} "
            f"({pcbnew.ToMM(position.x):.3f},{pcbnew.ToMM(position.y):.3f}) "
            f"{item_uuid} {details}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
