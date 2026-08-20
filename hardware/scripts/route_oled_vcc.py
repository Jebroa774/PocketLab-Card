"""Close OLED VCC while preserving the split-prone L3 AUX5 plane.

The OLED VCC pin exits through the narrow corridor between R105 and the
charge-pump route.  The nearby OLED_C1P horizontal segment is reduced to the
project minimum width, which leaves full 0.20-mm clearance around a standard
0.45/0.20-mm through via.  A short same-net L3 copper bridge keeps the
`+5V_AUX` distribution polygon connected around the new signal clearance.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil

import pcbnew

from restore_baseline_net import copper_blocks
from route_plane_fanouts import item_key


C1P_SEGMENT_UUID = "f4fd6c4c-dd87-4d5a-841f-01fce0d205f9"
OLED_F_UUID = "cdd92236-43ba-42cd-b837-8ee9ae01be62"
OLED_VIA_UUID = "c9b2ca2e-7424-48e4-95d8-cd06ad2eff52"
OLED_L3_UUID = "c2af9351-cf67-47c7-ba7a-631563b2e259"
AUX5_BRIDGE_UUID = "713acfc3-f3ef-57a8-951e-9662ae1f17f5"

OLED_LEFT = (80.850000, 63.600000)
OLED_RIGHT = (84.650000, 63.420000)
OLED_PAD = (85.900000, 63.375000)
AUX5_LEFT = (81.000000, 64.800000)
AUX5_RIGHT = (84.800000, 65.250000)

WIDTH_RE = re.compile(r"\(width\s+(-?\d+(?:\.\d+)?)\)")


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
        f"\t\t(start {start[0]:.6f} {start[1]:.6f})\n"
        f"\t\t(end {end[0]:.6f} {end[1]:.6f})\n"
        f"\t\t(width {width:.6f})\n"
        "\t\t(locked yes)\n"
        f"\t\t(layer \"{layer}\")\n"
        f"\t\t(net \"{net_name}\")\n"
        f"\t\t(uuid \"{item_uuid}\")\n"
        "\t)\n"
    )


def via(at: tuple[float, float], item_uuid: str) -> str:
    return (
        "\t(via\n"
        f"\t\t(at {at[0]:.6f} {at[1]:.6f})\n"
        "\t\t(size 0.450000)\n"
        "\t\t(drill 0.200000)\n"
        "\t\t(layers \"F.Cu\" \"B.Cu\")\n"
        "\t\t(locked yes)\n"
        "\t\t(net \"/OLED_VCC\")\n"
        f"\t\t(uuid \"{item_uuid}\")\n"
        "\t)\n"
    )


def route_text(text: str) -> str:
    blocks = {item_uuid: (start, end, kind, text[start:end]) for start, end, kind, item_uuid, _net in copper_blocks(text)}
    if C1P_SEGMENT_UUID not in blocks:
        raise RuntimeError("Reviewed OLED_C1P corridor segment is missing")
    c1p_start, c1p_end, c1p_kind, c1p_block = blocks[C1P_SEGMENT_UUID]
    if c1p_kind != "segment":
        raise RuntimeError("Reviewed OLED_C1P UUID no longer identifies a segment")
    width_match = WIDTH_RE.search(c1p_block)
    if not width_match:
        raise RuntimeError("Reviewed OLED_C1P segment has no width")
    current_width = float(width_match.group(1))
    if abs(current_width - 0.15) > 1e-9:
        narrowed = WIDTH_RE.sub("(width 0.150000)", c1p_block, count=1)
        text = text[:c1p_start] + narrowed + text[c1p_end:]

    addition_ids = {OLED_F_UUID, OLED_VIA_UUID, OLED_L3_UUID, AUX5_BRIDGE_UUID}
    present = addition_ids.intersection(blocks)
    if present:
        if present != addition_ids:
            raise RuntimeError("Partial OLED VCC route already exists")
        return text

    additions = (
        segment(
            OLED_RIGHT,
            OLED_PAD,
            width=0.15,
            layer="F.Cu",
            net_name="/OLED_VCC",
            item_uuid=OLED_F_UUID,
        )
        + via(OLED_RIGHT, OLED_VIA_UUID)
        + segment(
            OLED_LEFT,
            OLED_RIGHT,
            width=0.15,
            layer="In2.Cu",
            net_name="/OLED_VCC",
            item_uuid=OLED_L3_UUID,
        )
        + segment(
            AUX5_LEFT,
            AUX5_RIGHT,
            width=0.20,
            layer="In2.Cu",
            net_name="/+5V_AUX",
            item_uuid=AUX5_BRIDGE_UUID,
        )
    )
    insertion = text.find("\n\t(zone\n")
    if insertion < 0:
        insertion = text.rfind("\n)")
    if insertion < 0:
        raise RuntimeError("Could not locate copper insertion point")
    return text[:insertion] + "\n" + additions + text[insertion:]


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


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    text = route_text(args.input.resolve().read_text(encoding="utf-8"))
    output_path.write_text(text, encoding="utf-8", newline="\n")
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))

    board = pcbnew.LoadBoard(str(output_path))
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    checks = (
        ("OLED_VCC", pad(reloaded, "C615", "1"), pad(reloaded, "J8", "16")),
        ("OLED_C1P", pad(reloaded, "C611", "1"), pad(reloaded, "J8", "3")),
        ("+5V_AUX", pad(reloaded, "J5", "29"), pad(reloaded, "U15", "6")),
    )
    failed = [name for name, first, second in checks if not connected(reloaded, first, second)]
    if failed:
        raise RuntimeError(f"OLED route connectivity failed: {', '.join(failed)}")
    connectivity = reloaded.GetConnectivity()
    connectivity.RecalculateRatsnest()
    print(
        f"Saved OLED VCC candidate: {output_path}; "
        f"unconnected={int(connectivity.GetUnconnectedCount(False))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
