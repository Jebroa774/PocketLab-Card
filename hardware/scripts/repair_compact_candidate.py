"""Apply reviewed compact-layout repairs to a routed PCB candidate.

This pass deliberately works on a candidate copy.  It restores a small set of
0805 crossover resistors whose wider pin spacing is electrically cleaner than
forcing 0402 parts into existing route crossings, and it smooths only the
short local routes that currently create DRC errors or visually awkward
detours.  The authoritative PCB is never overwritten directly.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
import shutil

import pcbnew


RESTORE_R0805 = frozenset(
    {"R105", "R108", "R119", "R129", "R201", "R202", "R701", "R735"}
)

R0805_PARTS = {
    "R105": ("UNI-ROYAL", "0805W8F2201T5E", "C17520"),
    "R108": ("UNI-ROYAL", "0805W8F1002T5E", "C17414"),
    "R119": ("UNI-ROYAL", "0805W8F1002T5E", "C17414"),
    "R129": ("UNI-ROYAL", "0805W8F0000T5E", "C17477"),
    "R201": ("UNI-ROYAL", "0805W8F220JT5E", "C17561"),
    "R202": ("UNI-ROYAL", "0805W8F220JT5E", "C17561"),
    "R701": ("UNI-ROYAL", "0805W8F3301T5E", "C26010"),
    "R735": ("UNI-ROYAL", "0805W8F1003T5E", "C149504"),
}

TOLERANCE_MM = 0.002


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(
        pcbnew.FromMM(position[0]), pcbnew.FromMM(position[1])
    )


def close(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return math.dist(left, right) <= TOLERANCE_MM


def get_or_add_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def find_copper(board: pcbnew.BOARD, uuid: str) -> pcbnew.BOARD_CONNECTED_ITEM:
    for item in board.GetTracks():
        if item.m_Uuid.AsString() == uuid:
            return item
    raise RuntimeError(f"Copper UUID not found: {uuid}")


def move_uuid_point(
    board: pcbnew.BOARD,
    uuid: str,
    old: tuple[float, float],
    new: tuple[float, float],
) -> int:
    item = find_copper(board, uuid)
    changed = 0
    if isinstance(item, pcbnew.PCB_VIA):
        if close(xy(item.GetPosition()), old):
            item.SetPosition(point(new))
            changed += 1
    else:
        if close(xy(item.GetStart()), old):
            item.SetStart(point(new))
            changed += 1
        if close(xy(item.GetEnd()), old):
            item.SetEnd(point(new))
            changed += 1
    if changed == 0:
        raise RuntimeError(f"Copper {uuid} does not contain point {old}")
    return changed


def move_net_point(
    board: pcbnew.BOARD,
    net_name: str,
    old: tuple[float, float],
    new: tuple[float, float],
) -> int:
    changed = 0
    for item in board.GetTracks():
        if item.GetNetname() != net_name:
            continue
        if isinstance(item, pcbnew.PCB_VIA):
            if close(xy(item.GetPosition()), old):
                item.SetPosition(point(new))
                changed += 1
            continue
        if close(xy(item.GetStart()), old):
            item.SetStart(point(new))
            changed += 1
        if close(xy(item.GetEnd()), old):
            item.SetEnd(point(new))
            changed += 1
    if changed == 0:
        raise RuntimeError(f"No {net_name} copper found at {old}")
    return changed


def delete_uuid(board: pcbnew.BOARD, uuid: str) -> None:
    board.Delete(find_copper(board, uuid))


@dataclass
class PadEndpoint:
    number: str
    net_name: str
    touches: list[tuple[pcbnew.BOARD_ITEM, str]]


def collect_pad_endpoints(
    board: pcbnew.BOARD, footprint: pcbnew.FOOTPRINT
) -> list[PadEndpoint]:
    records: list[PadEndpoint] = []
    for pad in footprint.Pads():
        touches: list[tuple[pcbnew.BOARD_ITEM, str]] = []
        for item in board.GetTracks():
            if isinstance(item, pcbnew.PCB_VIA) or item.GetNetname() != pad.GetNetname():
                continue
            if pad.HitTest(item.GetStart()):
                touches.append((item, "start"))
            if pad.HitTest(item.GetEnd()):
                touches.append((item, "end"))
        records.append(PadEndpoint(pad.GetNumber(), pad.GetNetname(), touches))
    return records


def place_like(replacement: pcbnew.FOOTPRINT, target: pcbnew.FOOTPRINT) -> None:
    if replacement.GetLayer() != target.GetLayer():
        replacement.Flip(
            replacement.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT
        )
    replacement.SetPosition(target.GetPosition())
    replacement.SetOrientationDegrees(target.GetOrientationDegrees())


def restore_0805(
    board: pcbnew.BOARD, donor: pcbnew.BOARD, reference: str
) -> int:
    existing = board.FindFootprintByReference(reference)
    source = donor.FindFootprintByReference(reference)
    if existing is None or source is None:
        raise RuntimeError(f"Missing input/donor footprint: {reference}")
    if source.GetFPID().GetUniStringLibId() != "Resistor_SMD:R_0805_2012Metric":
        raise RuntimeError(f"Donor {reference} is not the reviewed 0805 footprint")

    records = collect_pad_endpoints(board, existing)
    replacement = pcbnew.Cast_to_FOOTPRINT(source.Duplicate(False))
    place_like(replacement, existing)

    replacement.SetReference(reference)
    replacement.SetValue(existing.GetValue())
    fields = dict(existing.GetFieldsText())
    manufacturer, mpn, lcsc = R0805_PARTS[reference]
    fields.update(Manufacturer=manufacturer, MPN=mpn, LCSC=lcsc)
    replacement.SetFields(fields)
    for name in replacement.GetFieldsText():
        if name != "Reference":
            replacement.GetField(name).SetVisible(False)
    replacement.SetDNP(existing.IsDNP())
    replacement.SetExcludedFromBOM(existing.IsExcludedFromBOM())
    replacement.SetExcludedFromPosFiles(existing.IsExcludedFromPosFiles())
    replacement.SetDuplicatePadNumbersAreJumpers(
        existing.GetDuplicatePadNumbersAreJumpers()
    )

    board.Delete(existing)
    board.Add(replacement)
    new_pads = {}
    for pad in replacement.Pads():
        pad.SetNet(get_or_add_net(board, pad.GetNetname()))
        new_pads[(pad.GetNumber(), pad.GetNetname())] = pad

    moved = 0
    for record in records:
        pad = new_pads.get((record.number, record.net_name))
        if pad is None:
            raise RuntimeError(f"No restored pad for {reference}.{record.number}")
        for item, endpoint in record.touches:
            if endpoint == "start":
                item.SetStart(pad.GetPosition())
            else:
                item.SetEnd(pad.GetPosition())
            moved += 1
    return moved


def set_fine_pitch_clearances(board: pcbnew.BOARD) -> int:
    changed = 0
    for reference in ("U7", "Q2", "Q3"):
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"Missing fine-pitch footprint: {reference}")
        for pad in footprint.Pads():
            if reference == "U7" or pad.GetNumber() in {"1", "2", "3", "4"}:
                pad.SetLocalClearance(pcbnew.FromMM(0.15))
                changed += 1
    return changed


def repair_local_routes(board: pcbnew.BOARD) -> int:
    changed = 0

    # Move two ground stitching vias away from neighbouring power lands.
    changed += move_net_point(
        board, "/GND", (64.463886, 26.010017), (65.0, 26.0)
    )
    changed += move_net_point(
        board, "/GND", (70.644265, 45.087625), (71.5, 44.8)
    )

    # Give the SELECT switch's signal land a clean assembly courtyard.
    changed += move_net_point(board, "/+3V3", (56.125, 54.5), (56.9, 54.3))

    # This ground spur duplicated the return plane and crossed LF_DIN_5V.
    delete_uuid(board, "1587ae75-f4b0-4198-9894-fddccfadc25c")

    # Smooth the LF clock dogleg around SW3 while retaining its layer change.
    changed += move_uuid_point(
        board,
        "c5c9bf89-120e-49a3-92a1-c7c87c458eca",
        (50.037499, 54.8),
        (50.45, 55.8),
    )
    lf_tail = find_copper(board, "433ecf34-5280-486a-9f87-e568e7ee0295")
    lf_tail.SetStart(point((50.45, 55.8)))
    lf_tail.SetEnd(point((50.45, 54.3)))
    changed += 2
    changed += move_net_point(
        board, "/LF_SCLK_5V", (50.037499, 54.55), (50.45, 54.3)
    )

    # Open the central VSYS channel slightly without changing its topology.
    for uuid, old, new in (
        ("9212acee-3229-4480-8459-70039d262415", (75.35, 46.25), (75.35, 46.4)),
        ("d58e5f7b-409c-4ef8-9890-f2a0c883ebfa", (75.35, 46.25), (75.35, 46.4)),
        ("d58e5f7b-409c-4ef8-9890-f2a0c883ebfa", (81.6, 46.25), (81.6, 46.4)),
        ("2ab13b35-cb6f-4e31-9f19-8d493f229356", (81.6, 46.25), (81.6, 46.4)),
        ("dd19a945-f112-44f3-8867-1892ec494fb5", (81.6, 46.25), (81.6, 46.4)),
    ):
        changed += move_uuid_point(board, uuid, old, new)

    # Straighten SPI_SCK through the narrow switch/U22 corridor.
    for uuid, old, new in (
        ("f57a9c24-e618-4c15-b317-533d0dc00199", (74.7875, 41.15), (75.15, 41.15)),
        ("560ba371-388c-4697-b80a-9f3d7703ea86", (74.7875, 41.15), (75.15, 41.15)),
        ("560ba371-388c-4697-b80a-9f3d7703ea86", (74.7875, 44.65), (75.15, 44.65)),
        ("4887d967-19bb-4fe6-870d-12ddc05739b7", (74.7875, 44.65), (75.15, 44.65)),
        ("4887d967-19bb-4fe6-870d-12ddc05739b7", (73.0375, 46.4), (72.65, 46.4)),
        ("723f2ba2-8109-446d-b5f5-c808f1e4fa49", (73.0375, 46.4), (72.65, 46.4)),
        ("723f2ba2-8109-446d-b5f5-c808f1e4fa49", (73.0375, 54.15), (72.65, 54.15)),
        ("cb80f3ae-9849-4b35-8343-25cc220bd33d", (73.0375, 54.15), (72.65, 54.15)),
    ):
        changed += move_uuid_point(board, uuid, old, new)

    # Nudge the long MOSI vertical by 0.05 mm to clear two ground escapes.
    changed += move_net_point(
        board, "/SPI_MOSI", (79.7125, 32.6), (79.7625, 32.6)
    )
    changed += move_net_point(
        board, "/SPI_MOSI", (79.7125, 37.35), (79.7625, 37.35)
    )
    return changed


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    donor_path = args.donor.resolve()
    output_path = args.output.resolve()
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file() or not donor_path.is_file():
        raise RuntimeError("Input and donor PCB must exist")
    if output_path == authoritative:
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    donor = pcbnew.LoadBoard(str(donor_path))
    endpoint_moves = 0
    for reference in sorted(RESTORE_R0805):
        endpoint_moves += restore_0805(board, donor, reference)
    local_clearances = set_fine_pitch_clearances(board)
    route_edits = repair_local_routes(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)

    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix)
        )
    print(
        f"Saved compact repair: {output_path}; restored_0805={len(RESTORE_R0805)}; "
        f"retargeted_endpoints={endpoint_moves}; local_clearance_pads={local_clearances}; "
        f"route_edits={route_edits}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
