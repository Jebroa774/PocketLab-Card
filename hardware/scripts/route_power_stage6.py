"""Route the two USB-C VBUS contacts to the input fuse.

The J1 VBUS contacts sit between signal contacts and two connector alignment
holes.  Each contact therefore uses a short 0.30-mm F.Cu escape around its
adjacent hole, changes layer outside the connector body, and widens to
0.60 mm on B.Cu.  The route joins F1 without disturbing the reviewed USB 2.0
data/CC copper.  Inner layers remain plane-only.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pcbnew

import route_lf_global as router


VBUS = "/VBUS_USB"
LOWER_AREA = "USB_VBUS_LOWER_NECKDOWN"
UPPER_AREA = "USB_VBUS_UPPER_NECKDOWN"
SHIELD_AREA = "USB_VBUS_SHIELD_NECKDOWN"

F_SEGMENTS = (
    ((98.555, 49.25), (99.15, 49.25), 0.30),
    ((99.15, 49.25), (99.50, 49.50), 0.30),
    ((99.50, 49.50), (100.20, 49.60), 0.30),
    ((100.20, 49.60), (100.80, 49.60), 0.30),
    ((98.555, 54.15), (99.15, 54.15), 0.30),
    ((99.15, 54.15), (99.50, 53.90), 0.30),
    ((99.50, 53.90), (100.20, 53.80), 0.30),
    ((100.20, 53.80), (100.80, 53.80), 0.30),
)

B_SEGMENTS = (
    ((100.80, 49.60), (100.80, 53.80), 0.60),
    ((100.80, 49.60), (100.80, 50.40), 0.50),
    ((100.80, 50.40), (98.60, 50.40), 0.50),
    ((98.60, 50.40), (98.11, 50.40), 0.20),
    ((98.11, 50.40), (98.11, 46.40), 0.20),
    ((98.11, 46.40), (97.70, 46.40), 0.20),
    ((97.70, 46.40), (96.30, 46.40), 0.50),
    ((96.30, 46.40), (96.30, 47.10), 0.50),
)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I_MM(*position)


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def close(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return math.dist(first, second) < 0.002


def net(board: pcbnew.BOARD) -> pcbnew.NETINFO_ITEM:
    item = board.FindNet(VBUS)
    if item is None:
        raise RuntimeError(f"PCB is missing {VBUS}")
    return item


def add_track(
    board: pcbnew.BOARD,
    start: tuple[float, float],
    end: tuple[float, float],
    width_mm: float,
    layer: int,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(start))
    track.SetEnd(point(end))
    track.SetWidth(pcbnew.FromMM(width_mm))
    track.SetLayer(layer)
    track.SetNet(net(board))
    track.SetLocked(True)
    board.Add(track)


def add_via(
    board: pcbnew.BOARD,
    position: tuple[float, float],
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(position))
    via.SetWidth(pcbnew.FromMM(0.70))
    via.SetDrill(pcbnew.FromMM(0.35))
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net(board))
    via.SetLocked(True)
    board.Add(via)


def add_rule_area(
    board: pcbnew.BOARD,
    name: str,
    corners: tuple[tuple[float, float], ...],
) -> None:
    if any(zone.GetZoneName() == name for zone in board.Zones()):
        raise RuntimeError(f"Input already contains {name}")
    area = pcbnew.ZONE(board)
    area.SetZoneName(name)
    area.SetLayer(pcbnew.F_Cu)
    area.SetIsRuleArea(True)
    area.SetDoNotAllowZoneFills(False)
    area.SetDoNotAllowTracks(False)
    area.SetDoNotAllowVias(False)
    area.SetDoNotAllowPads(False)
    area.SetDoNotAllowFootprints(False)
    outline = area.Outline()
    outline.NewOutline()
    for corner in corners:
        outline.Append(point(corner))
    board.Add(area)


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    return router.pad_by_reference(board, reference, number)


def validate(board: pcbnew.BOARD) -> None:
    for name in (LOWER_AREA, UPPER_AREA, SHIELD_AREA):
        if not any(zone.GetZoneName() == name for zone in board.Zones()):
            raise RuntimeError(f"Missing rule area {name}")

    expected_vias = ((100.80, 49.60), (100.80, 53.80))
    for position in expected_vias:
        if not any(
            isinstance(item, pcbnew.PCB_VIA)
            and item.GetNetname() == VBUS
            and close(xy(item.GetPosition()), position)
            for item in board.GetTracks()
        ):
            raise RuntimeError(f"Missing VBUS via at {position}")

    endpoints = (
        pad(board, "J1", "A4"),
        pad(board, "J1", "A9"),
        pad(board, "J1", "B4"),
        pad(board, "J1", "B9"),
        pad(board, "F1", "1"),
    )
    if any(item.GetNetname() != VBUS for item in endpoints):
        raise RuntimeError("VBUS endpoint net mismatch")
    if any(
        not router.already_connected(board, endpoints[0], item)
        for item in endpoints[1:]
    ):
        raise RuntimeError("Serialized PCB lost local USB-C VBUS connectivity")


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input PCB does not exist: {input_path}")
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    if any(item.GetNetname() == VBUS for item in board.GetTracks()):
        raise RuntimeError("Input already contains routed VBUS_USB copper")

    add_rule_area(
        board,
        LOWER_AREA,
        ((98.20, 48.85), (101.10, 48.85), (101.10, 50.05), (98.20, 50.05)),
    )
    add_rule_area(
        board,
        UPPER_AREA,
        ((98.20, 53.35), (101.10, 53.35), (101.10, 54.55), (98.20, 54.55)),
    )
    add_rule_area(
        board,
        SHIELD_AREA,
        ((97.90, 46.20), (98.75, 46.20), (98.75, 50.60), (97.90, 50.60)),
    )
    for start, end, width_mm in F_SEGMENTS:
        add_track(board, start, end, width_mm, pcbnew.F_Cu)
    for position in ((100.80, 49.60), (100.80, 53.80)):
        add_via(board, position)
    for start, end, width_mm in B_SEGMENTS:
        add_track(board, start, end, width_mm, pcbnew.B_Cu)

    validate(board)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    validate(pcbnew.LoadBoard(str(output_path)))
    print("Completed the local USB-C VBUS-to-F1 route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
