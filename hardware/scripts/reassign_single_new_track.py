"""Move one safely anchored candidate track to another copper layer.

Both endpoints must already touch a same-net through via or all-layer pad, so
the layer change preserves connectivity.  Candidates are ranked by their
participation in the current DRC report, allowing quick one-change trials.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

import pcbnew

from prune_new_drc_conflicts import geometry_key, uuid_text
from reassign_new_track_layers import COPPER_LAYERS, occupied_layers


TYPE_WEIGHT = {
    "shorting_items": 8,
    "tracks_crossing": 6,
    "clearance": 3,
    "items_not_allowed": 3,
}
LAYER_BY_NAME = {
    "F.Cu": pcbnew.F_Cu,
    "In1.Cu": pcbnew.In1_Cu,
    "In2.Cu": pcbnew.In2_Cu,
    "B.Cu": pcbnew.B_Cu,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rank", type=int, required=True)
    parser.add_argument("--layer", choices=tuple(LAYER_BY_NAME), required=True)
    parser.add_argument("--skip-fill-zones", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    hardware_dir = Path(__file__).resolve().parent.parent
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if args.output.resolve() in {
        authoritative,
        args.base.resolve(),
        args.candidate.resolve(),
    }:
        raise RuntimeError("output must be a separate non-authoritative board")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")
    if args.rank < 0:
        raise RuntimeError("rank must be non-negative")

    base = pcbnew.LoadBoard(str(args.base.resolve()))
    board = pcbnew.LoadBoard(str(args.candidate.resolve()))
    base_keys = {geometry_key(item) for item in base.GetTracks()}

    anchors: set[tuple[int, int, int]] = set()
    for item in board.GetTracks():
        if isinstance(item, pcbnew.PCB_VIA):
            position = item.GetPosition()
            anchors.add((position.x, position.y, item.GetNetCode()))
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if len(occupied_layers(pad)) == len(COPPER_LAYERS):
                position = pad.GetPosition()
                anchors.add((position.x, position.y, pad.GetNetCode()))

    movable = {}
    for item in board.GetTracks():
        if isinstance(item, pcbnew.PCB_VIA) or geometry_key(item) in base_keys:
            continue
        start = item.GetStart()
        end = item.GetEnd()
        net = item.GetNetCode()
        if (start.x, start.y, net) in anchors and (end.x, end.y, net) in anchors:
            movable[uuid_text(item)] = item

    scores: Counter[str] = Counter()
    report = json.loads(args.drc.read_text(encoding="utf-8"))
    for violation in report.get("violations", []):
        weight = TYPE_WEIGHT.get(violation.get("type"), 0)
        if not weight:
            continue
        for item_uuid in {
            entry.get("uuid", "") for entry in violation.get("items", [])
        }:
            if item_uuid in movable:
                scores[item_uuid] += weight

    order = sorted(
        movable,
        key=lambda item_uuid: (
            scores[item_uuid],
            pcbnew.ToMM(movable[item_uuid].GetLength()),
        ),
        reverse=True,
    )
    if args.rank >= len(order):
        raise RuntimeError(f"rank {args.rank} exceeds {len(order)} movable tracks")

    selected_uuid = order[args.rank]
    selected = movable[selected_uuid]
    old_layer = selected.GetLayer()
    new_layer = LAYER_BY_NAME[args.layer]
    selected.SetLayer(new_layer)
    if not args.skip_fill_zones:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(args.output.resolve()), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix)
        )
    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    print(
        f"REASSIGNED rank={args.rank} uuid={selected_uuid} "
        f"net={selected.GetNetname()} score={scores[selected_uuid]} "
        f"length={pcbnew.ToMM(selected.GetLength()):.3f} "
        f"{board.GetLayerName(old_layer)}->{board.GetLayerName(new_layer)} "
        f"opens={int(connectivity.GetUnconnectedCount(False))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
