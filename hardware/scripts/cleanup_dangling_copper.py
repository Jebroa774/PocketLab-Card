"""Remove only copper items explicitly reported as dangling by KiCad DRC.

This is intended for migration candidates after footprint replacement.  The
DRC JSON supplies stable UUIDs, so the pass cannot accidentally select nearby
valid copper by geometry.  The authoritative PCB is never overwritten.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pcbnew


DANGLING_TYPES = frozenset({"track_dangling", "via_dangling"})


def dangling_uuids(report_path: Path) -> set[str]:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    result: set[str] = set()
    for violation in report.get("violations", []):
        if violation.get("type") not in DANGLING_TYPES:
            continue
        for item in violation.get("items", []):
            uuid = item.get("uuid")
            if uuid:
                result.add(uuid)
    return result


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--remove-uuid",
        action="append",
        default=[],
        help="additional reviewed copper UUID to remove (repeatable)",
    )
    parser.add_argument(
        "--remove-net",
        action="append",
        default=[],
        help="reviewed net whose routed copper is being rebuilt (repeatable)",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    report_path = args.drc.resolve()
    output_path = args.output.resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if not report_path.is_file():
        raise RuntimeError(f"DRC report does not exist: {report_path}")
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    requested = dangling_uuids(report_path) | set(args.remove_uuid)
    if not requested:
        raise RuntimeError("DRC report contains no dangling copper UUIDs")

    board = pcbnew.LoadBoard(str(input_path))
    removed: list[str] = []
    remove_nets = {
        name if name.startswith("/") else f"/{name}" for name in args.remove_net
    }
    for item in list(board.Tracks()):
        uuid = item.m_Uuid.AsString()
        if uuid in requested or item.GetNetname() in remove_nets:
            # RemoveNative transfers ownership cleanly in KiCad's Python
            # bindings.  Repeated BOARD.Remove calls can leave stale SWIG
            # wrappers and crash when a second cleanup pass is saved.
            board.RemoveNative(item)
            removed.append(uuid)

    missing = requested.difference(removed)
    if missing:
        raise RuntimeError(
            "DRC dangling UUIDs were not found in board copper: "
            + ", ".join(sorted(missing))
        )

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    print(
        f"Saved cleaned PCB: {output_path}; removed_dangling={len(removed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
