"""Reconnect one migrated pad by retargeting its reviewed baseline end copper.

This is intentionally narrower than restoring a complete net: only baseline
segments/vias that touch the requested old pad centre are copied, and only
that endpoint is moved to the new pad centre.  The source PCB is never
overwritten.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil

import pcbnew

from restore_baseline_net import (
    copper_blocks,
    coord_key,
    footprints,
    retarget_block,
    xy,
)


def block_touches(block: str, position: tuple[float, float]) -> bool:
    from restore_baseline_net import POINT_RE

    target = coord_key(position)
    return any(
        coord_key((float(match.group(2)), float(match.group(3)))) == target
        for match in POINT_RE.finditer(block)
    )


def replace_or_add(
    board_text: str,
    source_blocks: dict[str, str],
) -> tuple[str, int, int]:
    replacements: list[tuple[int, int, str]] = []
    present: set[str] = set()
    for start, end, _kind, uuid, _net in copper_blocks(board_text):
        if uuid not in source_blocks:
            continue
        replacements.append((start, end, source_blocks[uuid]))
        present.add(uuid)
    for start, end, block in sorted(replacements, reverse=True):
        board_text = board_text[:start] + block + board_text[end:]

    additions = [block for uuid, block in source_blocks.items() if uuid not in present]
    if additions:
        insertion = board_text.find("\n\t(zone\n")
        if insertion < 0:
            insertion = board_text.rfind("\n)")
        board_text = board_text[:insertion] + "\n" + "".join(additions) + board_text[insertion:]
    return board_text, len(replacements), len(additions)


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pad", required=True, help="One REF.PAD label")
    parser.add_argument("--max-shift", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")
    try:
        reference, number = args.pad.rsplit(".", 1)
    except ValueError as error:
        raise RuntimeError("--pad must be REF.PAD") from error

    baseline_path = args.baseline.resolve()
    input_path = args.input.resolve()
    baseline = pcbnew.LoadBoard(str(baseline_path))
    board = pcbnew.LoadBoard(str(input_path))
    old_footprint = footprints(baseline).get(reference)
    new_footprint = footprints(board).get(reference)
    if old_footprint is None or new_footprint is None:
        raise RuntimeError(f"Footprint missing in baseline or candidate: {reference}")
    old_pad = next((pad for pad in old_footprint.Pads() if pad.GetNumber() == number), None)
    new_pad = next((pad for pad in new_footprint.Pads() if pad.GetNumber() == number), None)
    if old_pad is None or new_pad is None:
        raise RuntimeError(f"Pad missing in baseline or candidate: {args.pad}")
    if old_pad.GetNetname() != new_pad.GetNetname():
        raise RuntimeError(f"Net changed for {args.pad}")
    old_position = xy(old_pad.GetPosition())
    new_position = xy(new_pad.GetPosition())
    shift = math.dist(old_position, new_position)
    if shift <= 0.002:
        raise RuntimeError(f"Pad did not move: {args.pad}")
    if shift > args.max_shift:
        raise RuntimeError(
            f"Pad shift {shift:.3f} mm exceeds --max-shift {args.max_shift:.3f} mm"
        )

    baseline_text = baseline_path.read_text(encoding="utf-8")
    source_blocks: dict[str, str] = {}
    retarget = {coord_key(old_position): new_position}
    for start, end, _kind, uuid, net in copper_blocks(baseline_text):
        block = baseline_text[start:end]
        if net == old_pad.GetNetname() and block_touches(block, old_position):
            source_blocks[uuid] = retarget_block(block, retarget)
    if not source_blocks:
        raise RuntimeError(f"No baseline copper touches {args.pad}")

    restored, replaced, added = replace_or_add(
        input_path.read_text(encoding="utf-8"), source_blocks
    )
    output_path.write_text(restored, encoding="utf-8", newline="\n")
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(
        f"Retargeted {args.pad} {old_pad.GetNetname()}: shift={shift:.3f} mm; "
        f"replaced={replaced}; added={added}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
