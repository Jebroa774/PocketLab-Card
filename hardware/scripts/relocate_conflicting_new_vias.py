"""Relocate a small batch of high-conflict candidate-added vias."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import shutil

import pcbnew

from prune_new_drc_conflicts import geometry_key, uuid_text


COPPER_LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
TYPE_WEIGHTS = {
    "shorting_items": 6,
    "holes_co_located": 6,
    "hole_to_hole": 5,
    "hole_clearance": 4,
    "clearance": 2,
    "solder_mask_bridge": 1,
}


def mm_point(vector: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vector.x), pcbnew.ToMM(vector.y)


def point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared < 1e-12:
        return math.dist(point, start)
    position = max(
        0.0,
        min(
            1.0,
            ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy)
            / length_squared,
        ),
    )
    projection = (start[0] + position * dx, start[1] + position * dy)
    return math.dist(point, projection)


def add_stub(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    layer: int,
    width: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I_MM(*start))
    track.SetEnd(pcbnew.VECTOR2I_MM(*end))
    track.SetWidth(width)
    track.SetLayer(layer)
    track.SetNet(net)
    track.SetLocked(True)
    board.Add(track)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-vias", type=int, default=10)
    parser.add_argument(
        "--skip-vias",
        type=int,
        default=0,
        help="skip this many highest-scoring vias before selecting the batch",
    )
    parser.add_argument("--min-score", type=int, default=8)
    parser.add_argument("--clearance", type=float, default=0.18)
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
    if args.max_vias < 1 or args.min_score < 1 or args.skip_vias < 0:
        raise RuntimeError("via limits must be positive and skip-vias non-negative")

    base = pcbnew.LoadBoard(str(args.base.resolve()))
    board = pcbnew.LoadBoard(str(args.candidate.resolve()))
    base_keys = {geometry_key(item) for item in base.GetTracks()}
    new_vias = {
        uuid_text(item): item
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA) and geometry_key(item) not in base_keys
    }
    new_tracks = {
        uuid_text(item): item
        for item in board.GetTracks()
        if not isinstance(item, pcbnew.PCB_VIA) and geometry_key(item) not in base_keys
    }
    older_tracks = [
        item
        for item in board.GetTracks()
        if not isinstance(item, pcbnew.PCB_VIA) and uuid_text(item) not in new_tracks
    ]
    pads = [pad for footprint in board.GetFootprints() for pad in footprint.Pads()]

    report = json.loads(args.drc.read_text(encoding="utf-8"))
    scores: Counter[str] = Counter()
    for violation in report.get("violations", []):
        weight = TYPE_WEIGHTS.get(violation.get("type"), 0)
        if not weight:
            continue
        for item in violation.get("items", []):
            item_uuid = item.get("uuid", "")
            if item_uuid in new_vias:
                scores[item_uuid] += weight

    ranked = [
        item_uuid
        for item_uuid, score in scores.most_common()
        if score >= args.min_score
    ]
    selected = ranked[args.skip_vias : args.skip_vias + args.max_vias]
    bbox = board.GetBoardEdgesBoundingBox()
    left = pcbnew.ToMM(bbox.GetLeft()) + 0.65
    right = pcbnew.ToMM(bbox.GetRight()) - 0.65
    top = pcbnew.ToMM(bbox.GetTop()) + 0.65
    bottom = pcbnew.ToMM(bbox.GetBottom()) - 0.65

    moved = 0
    skipped = 0
    total_stubs = 0
    for item_uuid in selected:
        via = new_vias[item_uuid]
        old = mm_point(via.GetPosition())
        net_code = via.GetNetCode()
        direct = []
        for track in new_tracks.values():
            if track.GetNetCode() != net_code:
                continue
            if mm_point(track.GetStart()) == old or mm_point(track.GetEnd()) == old:
                direct.append(track)
        if not direct:
            skipped += 1
            continue

        anchor_layers: set[int] = set()
        for pad in pads:
            if pad.GetNetCode() != net_code or mm_point(pad.GetPosition()) != old:
                continue
            pad_layers = {layer for layer in COPPER_LAYERS if pad.IsOnLayer(layer)}
            if len(pad_layers) == len(COPPER_LAYERS):
                anchor_layers.add(direct[0].GetLayer())
            else:
                anchor_layers.update(pad_layers)
        for track in older_tracks:
            if track.GetNetCode() != net_code:
                continue
            if (
                point_segment_distance(
                    old, mm_point(track.GetStart()), mm_point(track.GetEnd())
                )
                < 0.002
            ):
                anchor_layers.add(track.GetLayer())
        if not anchor_layers and len(direct) < 2:
            for zone in board.Zones():
                if zone.GetNetCode() != net_code:
                    continue
                try:
                    if zone.HitTest(via.GetPosition()):
                        anchor_layers.update(
                            layer for layer in COPPER_LAYERS if zone.IsOnLayer(layer)
                        )
                except TypeError:
                    pass
        if not anchor_layers and len(direct) < 2:
            skipped += 1
            continue

        via_radius = pcbnew.ToMM(via.GetWidth(pcbnew.F_Cu)) / 2.0
        via_drill_radius = pcbnew.ToMM(via.GetDrillValue()) / 2.0

        def position_cost(position: tuple[float, float]) -> float:
            cost = math.dist(old, position) * 0.2
            for other in board.GetTracks():
                if other is via or other.GetNetCode() == net_code:
                    continue
                if isinstance(other, pcbnew.PCB_VIA):
                    distance = math.dist(position, mm_point(other.GetPosition()))
                    copper_limit = (
                        via_radius
                        + pcbnew.ToMM(other.GetWidth(pcbnew.F_Cu)) / 2.0
                        + args.clearance
                    )
                    hole_limit = (
                        via_drill_radius
                        + pcbnew.ToMM(other.GetDrillValue()) / 2.0
                        + 0.25
                    )
                    if distance < copper_limit:
                        cost += 2000.0 + (copper_limit - distance) * 100.0
                    if distance < hole_limit:
                        cost += 2000.0 + (hole_limit - distance) * 100.0
                else:
                    distance = point_segment_distance(
                        position, mm_point(other.GetStart()), mm_point(other.GetEnd())
                    )
                    limit = (
                        via_radius
                        + pcbnew.ToMM(other.GetWidth()) / 2.0
                        + args.clearance
                    )
                    if distance < limit:
                        cost += 1500.0 + (limit - distance) * 100.0
            for pad in pads:
                if pad.GetNetCode() == net_code:
                    continue
                distance = math.dist(position, mm_point(pad.GetPosition()))
                size = pad.GetSize()
                copper_limit = (
                    via_radius
                    + max(pcbnew.ToMM(size.x), pcbnew.ToMM(size.y)) / 2.0
                    + args.clearance
                )
                if distance < copper_limit:
                    cost += 1800.0 + (copper_limit - distance) * 100.0
                drill = pad.GetDrillSize()
                if drill.x > 0 and drill.y > 0:
                    hole_limit = (
                        via_drill_radius
                        + max(pcbnew.ToMM(drill.x), pcbnew.ToMM(drill.y)) / 2.0
                        + 0.25
                    )
                    if distance < hole_limit:
                        cost += 2000.0 + (hole_limit - distance) * 100.0
            # Penalize each proposed anchor stub crossing older foreign tracks.
            for layer in anchor_layers:
                for track in older_tracks:
                    if track.GetLayer() != layer or track.GetNetCode() == net_code:
                        continue
                    # Sampling the midpoint is sufficient for these short stubs.
                    midpoint = ((old[0] + position[0]) / 2, (old[1] + position[1]) / 2)
                    limit = (
                        pcbnew.ToMM(track.GetWidth()) / 2.0 + args.clearance + 0.10
                    )
                    if (
                        point_segment_distance(
                            midpoint,
                            mm_point(track.GetStart()),
                            mm_point(track.GetEnd()),
                        )
                        < limit
                    ):
                        cost += 500.0
            return cost

        candidates = []
        for radius in (0.60, 0.80, 1.00, 1.20, 1.50, 1.80):
            for angle_index in range(16):
                angle = angle_index * math.pi / 8.0
                candidate = (
                    round((old[0] + radius * math.cos(angle)) / 0.025) * 0.025,
                    round((old[1] + radius * math.sin(angle)) / 0.025) * 0.025,
                )
                if left <= candidate[0] <= right and top <= candidate[1] <= bottom:
                    candidates.append((position_cost(candidate), candidate))
        if not candidates:
            skipped += 1
            continue
        current_cost = position_cost(old)
        best_cost, best = min(candidates)
        if best_cost >= current_cost - 1.0:
            skipped += 1
            continue

        for track in direct:
            if mm_point(track.GetStart()) == old:
                track.SetStart(pcbnew.VECTOR2I_MM(*best))
            if mm_point(track.GetEnd()) == old:
                track.SetEnd(pcbnew.VECTOR2I_MM(*best))
        stub_width = max(
            pcbnew.FromMM(0.15),
            min(track.GetWidth() for track in direct),
        )
        net = board.FindNet(via.GetNetname())
        for layer in anchor_layers:
            add_stub(board, net, layer, stub_width, old, best)
            total_stubs += 1
        via.SetPosition(pcbnew.VECTOR2I_MM(*best))
        moved += 1

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(args.output.resolve()), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix)
        )
    print(
        f"RELOCATED selected={len(selected)} moved={moved} skipped={skipped} "
        f"stubs={total_stubs} uuids={','.join(selected)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
