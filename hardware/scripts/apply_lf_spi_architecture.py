"""Apply the reviewed shared-SPI LF-RFID isolation architecture to a PCB.

The LF block reuses SPI SCK/MOSI/MISO instead of consuming three isolated
ESP32 routes.  U21 is a partial-power-down-safe SN74LV125AT, and U22 is an
active-high tri-state SN74LVC1G126 controlled by LF_RFID_EN.  Consequently the
switched-off LF block neither back-powers nor drives the shared SPI bus.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    footprint = board.FindFootprintByReference(reference)
    if footprint is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    matches = [candidate for candidate in footprint.Pads() if candidate.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}.{number} pad, got {len(matches)}")
    return matches[0]


def get_or_create_net(board: pcbnew.BOARD, net_name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(net_name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, net_name)
        board.Add(net)
    return net


def set_net(board: pcbnew.BOARD, reference: str, number: str, net_name: str) -> None:
    target = pad(board, reference, number)
    target.SetNet(get_or_create_net(board, net_name))


def set_field(footprint: pcbnew.FOOTPRINT, name: str, value: str) -> None:
    if not footprint.HasField(name):
        raise RuntimeError(f"{footprint.GetReference()} is missing field {name}")
    footprint.GetField(name).SetText(value)


def remove_pad_escape_to_first_via(board: pcbnew.BOARD, target: pcbnew.PAD) -> int:
    """Remove only the old local escape of a repurposed U21 pad.

    Plane fanouts may share the first via with other pads.  Walk same-net
    segments from the pad centre, include the segment that reaches a via, and
    stop there so the shared via and every downstream branch remain intact.
    """

    def nearby(first: tuple[int, int], second: tuple[int, int]) -> bool:
        # KiCad zone refill can round a serialized endpoint by one nanometre.
        return abs(first[0] - second[0]) <= 5 and abs(first[1] - second[1]) <= 5

    old_net = target.GetNetname()
    frontier = {(target.GetPosition().x, target.GetPosition().y)}
    visited_positions: set[tuple[int, int]] = set()
    reached_via_positions: set[tuple[int, int]] = set()
    removable: list[pcbnew.PCB_TRACK] = []
    tracks = [item for item in board.GetTracks() if not isinstance(item, pcbnew.PCB_VIA)]
    via_positions = {
        (item.GetPosition().x, item.GetPosition().y)
        for item in board.GetTracks()
        if isinstance(item, pcbnew.PCB_VIA) and item.GetNetname() == old_net
    }
    while frontier:
        position = frontier.pop()
        reached_via = next(
            (candidate for candidate in via_positions if nearby(position, candidate)),
            None,
        )
        if reached_via is not None:
            reached_via_positions.add(reached_via)
            continue
        if position in visited_positions:
            continue
        visited_positions.add(position)
        for item in tracks:
            if item in removable or item.GetNetname() != old_net:
                continue
            start = (item.GetStart().x, item.GetStart().y)
            end = (item.GetEnd().x, item.GetEnd().y)
            if not nearby(start, position) and not nearby(end, position):
                continue
            removable.append(item)
            frontier.add(end if nearby(start, position) else start)
    for item in removable:
        board.Delete(item)
    remaining_tracks = [
        item for item in board.GetTracks() if not isinstance(item, pcbnew.PCB_VIA)
    ]
    for item in list(board.GetTracks()):
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        position = (item.GetPosition().x, item.GetPosition().y)
        if not any(nearby(position, candidate) for candidate in reached_via_positions):
            continue
        has_branch = any(
            track.GetStart() != track.GetEnd()
            and (
                nearby((track.GetStart().x, track.GetStart().y), position)
                or nearby((track.GetEnd().x, track.GetEnd().y), position)
            )
            for track in remaining_tracks
        )
        if not has_branch:
            board.Delete(item)
    return len(removable)


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
    assignments = (
        ("U1", "11", "unconnected-(U1-IO18-Pad11)"),
        ("U1", "23", "unconnected-(U1-IO21-Pad23)"),
        ("U1", "28", "unconnected-(U1-IO35-Pad28)"),
        ("U21", "1", "/GND"),
        ("U21", "2", "/GND"),
        ("U21", "3", "unconnected-(U21-Pin_3-Pad3)"),
        ("U21", "4", "/GND"),
        ("U21", "5", "/SPI_SCK"),
        ("U21", "6", "/LF_SCLK_5V"),
        ("U21", "7", "/GND"),
        ("U21", "8", "unconnected-(U21-Pin_8-Pad8)"),
        ("U21", "9", "/GND"),
        ("U21", "10", "/GND"),
        ("U21", "11", "/LF_DIN_5V"),
        ("U21", "12", "/SPI_MOSI"),
        ("U21", "13", "/GND"),
        ("U21", "14", "/LF_5V"),
        ("U22", "1", "/LF_RFID_EN"),
        ("U22", "4", "/SPI_MISO"),
    )
    removed_segments = 0
    for reference, number, net_name in assignments:
        target = pad(board, reference, number)
        if reference == "U21" and target.GetNetname() != net_name:
            removed_segments += remove_pad_escape_to_first_via(board, target)
    for reference, number, net_name in assignments:
        set_net(board, reference, number, net_name)
    board.RemoveUnusedNets(None)

    u21 = board.FindFootprintByReference("U21")
    u22 = board.FindFootprintByReference("U22")
    c515 = board.FindFootprintByReference("C515")
    assert u21 is not None and u22 is not None and c515 is not None
    c515.SetValue("100nF LV-AT supply")
    u21.SetOrientationDegrees(0.0)
    u21.SetValue("SN74LV125ATPWR LF/SPI 3V3-TO-5V IOFF")
    set_field(u21, "MPN", "SN74LV125ATPWR")
    set_field(u21, "LCSC", "C2675655")
    u22.SetValue("SN74LVC1G126DBVR LF 5V-TO-3V3 TRI-STATE")
    set_field(u22, "MPN", "SN74LVC1G126DBVR")
    set_field(u22, "LCSC", "C7834")

    pcbnew.SaveBoard(str(output_path), board)
    reloaded = pcbnew.LoadBoard(str(output_path))
    expected = {(reference, number): net_name for reference, number, net_name in assignments}
    for (reference, number), net_name in expected.items():
        if pad(reloaded, reference, number).GetNetname() != net_name:
            raise RuntimeError(f"Save/reload lost {reference}.{number} net assignment")
    print(
        f"Saved shared-SPI LF architecture: {output_path}; "
        f"removed_old_U21_escape_segments={removed_segments}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
