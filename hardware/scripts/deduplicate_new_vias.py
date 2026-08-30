"""Remove electrically redundant candidate-added through vias."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew

from prune_new_drc_conflicts import geometry_key


COPPER_LAYERS = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)


def position_net(item: pcbnew.BOARD_CONNECTED_ITEM) -> tuple[int, int, int]:
    position = item.GetPosition()
    return position.x, position.y, item.GetNetCode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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

    base = pcbnew.LoadBoard(str(args.base.resolve()))
    candidate = pcbnew.LoadBoard(str(args.candidate.resolve()))
    base_keys = {geometry_key(item) for item in base.GetTracks()}

    existing_anchors: set[tuple[int, int, int]] = set()
    for item in base.GetTracks():
        if isinstance(item, pcbnew.PCB_VIA) and item.GetViaType() == pcbnew.VIATYPE_THROUGH:
            existing_anchors.add(position_net(item))
    for footprint in candidate.GetFootprints():
        for pad in footprint.Pads():
            if all(pad.IsOnLayer(layer) for layer in COPPER_LAYERS):
                existing_anchors.add(position_net(pad))

    new_vias = [
        item
        for item in candidate.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA) and geometry_key(item) not in base_keys
    ]
    kept_positions: set[tuple[int, int, int]] = set()
    redundant_existing = 0
    redundant_duplicate = 0
    for via in new_vias:
        key = position_net(via)
        if key in existing_anchors:
            candidate.Remove(via)
            redundant_existing += 1
        elif key in kept_positions:
            candidate.Remove(via)
            redundant_duplicate += 1
        else:
            kept_positions.add(key)

    pcbnew.SaveBoard(str(args.output.resolve()), candidate)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", args.output.with_suffix(suffix)
        )
    print(
        "DEDUPLICATED "
        f"new={len(new_vias)} kept={len(kept_positions)} "
        f"existing={redundant_existing} duplicates={redundant_duplicate}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
