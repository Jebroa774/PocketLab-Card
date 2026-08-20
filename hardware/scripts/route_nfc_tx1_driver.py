"""Route the PN532 TX1 driver pin to its matching-network inductor.

The short TX1 connection is boxed in by the LF clock on F.Cu and the LF data
fanout on B.Cu.  Two small, connectivity-neutral jogs free a conventional
through-via pair; the signal then crosses the congested area on In2.Cu.  In1.Cu
remains the uninterrupted ground plane.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import uuid

import pcbnew

from restore_baseline_net import copper_blocks
from route_plane_fanouts import item_key


NET_NAME = "/NFC_TX1"

LF_SCLK_UUID = "e15cc646-05c6-45a2-b63a-708be11a5e3e"
LF_DIN_ENTRY_UUID = "57de0201-f931-4f3a-a03a-f7a7115916eb"
LF_DIN_TRUNK_UUID = "fcf9954e-e5c5-41cb-a64d-dde23ab93c84"

LF_SCLK_ROUTE = (
    (60.287499, 40.800000),
    (59.740000, 41.200000),
    (59.740000, 42.500000),
    (60.287499, 42.900000),
    (60.287499, 52.300000),
)
LF_DIN_ENTRY_ROUTE = (
    (60.462500, 41.250000),
    (59.700000, 41.250000),
    (59.700000, 41.800000),
)
LF_DIN_TRUNK_ROUTE = (
    (59.700000, 41.800000),
    (59.700000, 46.500000),
    (60.212500, 46.500000),
)

INDUCTOR_PAD = (61.000000, 38.062500)
INDUCTOR_VIA = (60.500000, 37.700000)
PN532_VIA = (60.320000, 41.850000)
PN532_PAD = (62.062500, 41.850000)
TX1_F_IN = (INDUCTOR_PAD, INDUCTOR_VIA)
TX1_IN2 = (
    INDUCTOR_VIA,
    (61.000000, 39.000000),
    (61.000000, 40.200000),
    PN532_VIA,
)
TX1_F_OUT = (PN532_VIA, PN532_PAD)

LAYER_RE = re.compile(r'\(layer "([^"]+)"\)')
NET_RE = re.compile(r'\(net "([^"]+)"\)')
WIDTH_RE = re.compile(r"\(width\s+(-?\d+(?:\.\d+)?)\)")
UUID_NAMESPACE = uuid.UUID("4d562aae-59e7-4d15-bdb4-bcc64aff9170")


def fixed_uuid(name: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, name))


def fmt(value: float) -> str:
    return f"{value:.6f}"


def segment(
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    width: float,
    layer: str,
    net_name: str,
    item_uuid: str,
) -> str:
    return (
        "\t(segment\n"
        f"\t\t(start {fmt(start[0])} {fmt(start[1])})\n"
        f"\t\t(end {fmt(end[0])} {fmt(end[1])})\n"
        f"\t\t(width {fmt(width)})\n"
        "\t\t(locked yes)\n"
        f"\t\t(layer \"{layer}\")\n"
        f"\t\t(net \"{net_name}\")\n"
        f"\t\t(uuid \"{item_uuid}\")\n"
        "\t)\n"
    )


def via(position: tuple[float, float], item_uuid: str) -> str:
    return (
        "\t(via\n"
        f"\t\t(at {fmt(position[0])} {fmt(position[1])})\n"
        "\t\t(size 0.450000)\n"
        "\t\t(drill 0.200000)\n"
        "\t\t(layers \"F.Cu\" \"B.Cu\")\n"
        "\t\t(locked yes)\n"
        f"\t\t(net \"{NET_NAME}\")\n"
        f"\t\t(uuid \"{item_uuid}\")\n"
        "\t)\n"
    )


def replacement(
    block: str,
    route: tuple[tuple[float, float], ...],
    original_uuid: str,
    name: str,
) -> str:
    layer_match = LAYER_RE.search(block)
    net_match = NET_RE.search(block)
    width_match = WIDTH_RE.search(block)
    if not layer_match or not net_match or not width_match:
        raise RuntimeError(f"Selected segment is incomplete: {original_uuid}")
    return "".join(
        segment(
            start,
            end,
            width=float(width_match.group(1)),
            layer=layer_match.group(1),
            net_name=net_match.group(1),
            item_uuid=original_uuid if index == 0 else fixed_uuid(f"{name}-{index}"),
        )
        for index, (start, end) in enumerate(zip(route, route[1:]))
    )


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    matches = [candidate for candidate in footprint.Pads() if candidate.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}.{number} pad, got {len(matches)}")
    return matches[0]


def connected(board: pcbnew.BOARD, first: pcbnew.PAD, second: pcbnew.PAD) -> bool:
    board.BuildConnectivity()
    second_key = item_key(second)
    return any(
        item_key(candidate) == second_key
        for candidate in board.GetConnectivity().GetConnectedItems(first)
    )


def route_text(text: str) -> str:
    selected = {
        item_uuid: (start, end, block)
        for start, end, kind, item_uuid, _net in copper_blocks(text)
        if kind == "segment"
        for block in (text[start:end],)
        if item_uuid in {LF_SCLK_UUID, LF_DIN_ENTRY_UUID, LF_DIN_TRUNK_UUID}
    }
    expected = {LF_SCLK_UUID, LF_DIN_ENTRY_UUID, LF_DIN_TRUNK_UUID}
    if set(selected) != expected:
        missing = ", ".join(sorted(expected - set(selected)))
        raise RuntimeError(f"Reviewed corridor segment(s) missing: {missing}")

    edits = []
    for item_uuid, route, name in (
        (LF_SCLK_UUID, LF_SCLK_ROUTE, "lf-sclk"),
        (LF_DIN_ENTRY_UUID, LF_DIN_ENTRY_ROUTE, "lf-din-entry"),
        (LF_DIN_TRUNK_UUID, LF_DIN_TRUNK_ROUTE, "lf-din-trunk"),
    ):
        start, end, block = selected[item_uuid]
        edits.append((start, end, replacement(block, route, item_uuid, name)))
    for start, end, new_block in sorted(edits, reverse=True):
        text = text[:start] + new_block + text[end:]

    additions = []
    for name, layer, route in (
        ("tx1-f-in", "F.Cu", TX1_F_IN),
        ("tx1-in2", "In2.Cu", TX1_IN2),
        ("tx1-f-out", "F.Cu", TX1_F_OUT),
    ):
        additions.extend(
            segment(
                start,
                end,
                width=0.20,
                layer=layer,
                net_name=NET_NAME,
                item_uuid=fixed_uuid(f"{name}-{index}"),
            )
            for index, (start, end) in enumerate(zip(route, route[1:]))
        )
    additions.extend(
        via(position, fixed_uuid(name))
        for name, position in (
            ("tx1-inductor-via", INDUCTOR_VIA),
            ("tx1-pn532-via", PN532_VIA),
        )
    )
    insertion = text.find("\n\t(zone\n")
    if insertion < 0:
        insertion = text.rfind("\n)")
    if insertion < 0:
        raise RuntimeError("Could not locate copper insertion point")
    return text[:insertion] + "\n" + "".join(additions) + text[insertion:]


def copy_sidecars(hardware_dir: Path, output_path: Path) -> None:
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    authoritative = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == authoritative:
        raise RuntimeError("Refusing to overwrite the authoritative PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    inductor = pad(board, "L301", "1")
    pn532 = pad(board, "U2", "4")
    if inductor.GetNetname() != NET_NAME or pn532.GetNetname() != NET_NAME:
        raise RuntimeError("NFC TX1 endpoint assignment changed")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if connected(board, inductor, pn532):
        shutil.copyfile(input_path, output_path)
        copy_sidecars(hardware_dir, output_path)
        print(f"TX1 already connected; copied {output_path}", flush=True)
    else:
        staged_path = output_path.with_suffix(".native-stage.kicad_pcb")
        staged_path.write_text(
            route_text(input_path.read_text(encoding="utf-8")),
            encoding="utf-8",
            newline="\n",
        )
        routed = pcbnew.LoadBoard(str(staged_path))
        pcbnew.ZONE_FILLER(routed).Fill(routed.Zones())
        pcbnew.SaveBoard(str(output_path), routed)
        staged_path.unlink()
        copy_sidecars(hardware_dir, output_path)
        print(f"Saved NFC TX1 candidate: {output_path}; tracks=10; vias=2", flush=True)

    reloaded = pcbnew.LoadBoard(str(output_path))
    if not connected(reloaded, pad(reloaded, "L301", "1"), pad(reloaded, "U2", "4")):
        raise RuntimeError("L301.1 is still disconnected from U2.4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
