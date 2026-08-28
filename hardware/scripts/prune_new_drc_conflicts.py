"""Remove only newly added copper that participates in many routing DRC errors."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-score", type=int, required=True)
    parser.add_argument("--type", action="append")
    parser.add_argument(
        "--net",
        action="append",
        default=[],
        help="remove all candidate-added copper for this reviewed net",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.resolve() in {args.base.resolve(), args.candidate.resolve()}:
        raise RuntimeError("output must differ from base and candidate")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")

    base = pcbnew.LoadBoard(str(args.base.resolve()))
    candidate = pcbnew.LoadBoard(str(args.candidate.resolve()))
    base_keys = {geometry_key(item) for item in base.GetTracks()}
    candidate_items = list(candidate.GetTracks())
    new_by_uuid = {
        uuid_text(item): item
        for item in candidate_items
        if geometry_key(item) not in base_keys
    }

    report = json.loads(args.drc.read_text(encoding="utf-8"))
    selected_types = set(args.type or ROUTING_TYPES)
    scores = Counter()
    for violation in report.get("violations", []):
        if violation.get("type") not in selected_types:
            continue
        for item_uuid in {
            entry.get("uuid", "") for entry in violation.get("items", [])
        }:
            if item_uuid in new_by_uuid:
                scores[item_uuid] += 1

    selected_nets = {
        name if name.startswith("/") else f"/{name}" for name in args.net
    }
    selected = {
        item_uuid for item_uuid, score in scores.items() if score >= args.min_score
    }
    selected.update(
        item_uuid
        for item_uuid, item in new_by_uuid.items()
        if item.GetNetname() in selected_nets
    )
    removed_tracks = 0
    removed_vias = 0
    nets = Counter()
    for item_uuid in selected:
        item = new_by_uuid[item_uuid]
        nets[item.GetNetname()] += 1
        if isinstance(item, pcbnew.PCB_VIA):
            removed_vias += 1
        else:
            removed_tracks += 1
        candidate.Remove(item)

    pcbnew.SaveBoard(str(args.output.resolve()), candidate)
    hardware_dir = Path(__file__).resolve().parent.parent
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix))
    print(
        f"PRUNED threshold={args.min_score} tracks={removed_tracks} "
        f"vias={removed_vias} total={len(selected)}"
    )
    print("NETS " + " ".join(f"{net}:{count}" for net, count in nets.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
