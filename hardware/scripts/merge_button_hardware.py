"""Merge the reviewed three-button hardware into an existing routed PCB.

The placement-only builder is the source for the replacement footprints and
board labels.  This helper preserves every unrelated footprint, track, zone and
drawing in the routed input while replacing SW3/SW4, adding SW7/R607 and moving
the former BMP390 interrupt input to the SELECT net.  Button nets are returned
to the ratsnest because their endpoints changed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


BUTTON_FOOTPRINTS = ("SW3", "SW7", "SW4", "R607")
CLEARED_NETS = frozenset(
    {
        "/USER_BUTTON_A_N",
        "/USER_BUTTON_SELECT_N",
        "/USER_BUTTON_B_N",
        # These guarded-autorouter paths crossed the new, mechanically checked
        # three-button strip or its SELECT pull-up.  Return the complete nets
        # to the ratsnest instead of retaining dangling or hidden stubs.
        "/IR_LED_A1",
        "/GPIO43",
        "/NFC_LOADMOD",
        "/LF_DOUT_5V",
    }
)
BUTTON_LABELS = frozenset({"UP", "OK", "DOWN"})
SELECT_NET = "/USER_BUTTON_SELECT_N"
BMP_NC_NET = "unconnected-(U11-Pin_7-Pad7)"


def get_or_add_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is not None:
        return net
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def pad_by_number(footprint: pcbnew.FOOTPRINT, number: str) -> pcbnew.PAD:
    pads = [pad for pad in footprint.Pads() if pad.GetNumber() == number]
    if len(pads) != 1:
        raise RuntimeError(
            f"Expected exactly one {footprint.GetReference()} pad {number}, got {len(pads)}"
        )
    return pads[0]


def replace_footprint(
    board: pcbnew.BOARD, donor: pcbnew.BOARD, reference: str
) -> None:
    source = donor.FindFootprintByReference(reference)
    if source is None:
        raise RuntimeError(f"Placement donor is missing {reference}")
    existing = board.FindFootprintByReference(reference)
    if existing is not None:
        board.Delete(existing)

    pad_nets = [pad.GetNetname() for pad in source.Pads()]
    replacement = pcbnew.Cast_to_FOOTPRINT(source.Duplicate(False))
    board.Add(replacement)
    replacement.SetReference(reference)
    replacement_pads = list(replacement.Pads())
    if len(replacement_pads) != len(pad_nets):
        raise RuntimeError(f"Pad-count changed while duplicating {reference}")
    for pad, net_name in zip(replacement_pads, pad_nets, strict=True):
        pad.SetNet(get_or_add_net(board, net_name))


def merge_button_hardware(board: pcbnew.BOARD, donor: pcbnew.BOARD) -> None:
    for track in list(board.GetTracks()):
        if track.GetNetname() in CLEARED_NETS:
            board.Delete(track)

    for reference in BUTTON_FOOTPRINTS:
        replace_footprint(board, donor, reference)

    u9 = board.FindFootprintByReference("U9")
    u11 = board.FindFootprintByReference("U11")
    if u9 is None or u11 is None:
        raise RuntimeError("U9/U11 are required for the SELECT/BMP390 reassignment")
    pad_by_number(u9, "11").SetNet(get_or_add_net(board, SELECT_NET))
    pad_by_number(u11, "7").SetNet(get_or_add_net(board, BMP_NC_NET))

    old_bmp_net = board.FindNet("/BMP_INT")
    if old_bmp_net is not None:
        still_used = any(
            pad.GetNetname() == "/BMP_INT"
            for footprint in board.GetFootprints()
            for pad in footprint.Pads()
        ) or any(track.GetNetname() == "/BMP_INT" for track in board.GetTracks())
        if still_used:
            raise RuntimeError("BMP_INT still has copper or pads after reassignment")
        board.Delete(old_bmp_net)

    for drawing in list(board.GetDrawings()):
        if isinstance(drawing, pcbnew.PCB_TEXT) and drawing.GetText() in BUTTON_LABELS:
            board.Delete(drawing)
    copied_labels: set[tuple[str, int]] = set()
    for drawing in donor.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        if drawing.GetText() not in BUTTON_LABELS:
            continue
        key = (drawing.GetText(), drawing.GetLayer())
        board.Add(drawing.Duplicate())
        copied_labels.add(key)
    expected_labels = {
        (label, layer)
        for label in BUTTON_LABELS
        for layer in (pcbnew.F_SilkS, pcbnew.F_Fab)
    }
    if copied_labels != expected_labels:
        raise RuntimeError(
            f"Button-label donor mismatch: missing={sorted(expected_labels - copied_labels)}"
        )


def validate(board: pcbnew.BOARD) -> None:
    references = [footprint.GetReference() for footprint in board.GetFootprints()]
    if len(references) != 266 or len(references) != len(set(references)):
        raise RuntimeError(
            f"Expected 266 unique footprints after merge, got {len(references)}"
        )
    expected = {
        ("SW3", "1"): "/USER_BUTTON_A_N",
        ("SW7", "1"): SELECT_NET,
        ("SW4", "1"): "/USER_BUTTON_B_N",
        ("R607", "1"): SELECT_NET,
        ("U9", "11"): SELECT_NET,
        ("U11", "7"): BMP_NC_NET,
    }
    for (reference, number), net_name in expected.items():
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"Merged PCB is missing {reference}")
        matching = [pad for pad in footprint.Pads() if pad.GetNumber() == number]
        if not matching or {pad.GetNetname() for pad in matching} != {net_name}:
            raise RuntimeError(f"{reference}.{number} is not on {net_name}")
    retained = sorted(
        {track.GetNetname() for track in board.GetTracks() if track.GetNetname() in CLEARED_NETS}
    )
    if retained:
        raise RuntimeError("Changed button nets retained stale copper: " + ", ".join(retained))


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
    main_board = (hardware_dir / "PocketLab-Card.kicad_pcb").resolve()
    if not input_path.is_file() or not donor_path.is_file():
        raise RuntimeError("Input and placement-donor PCBs must exist")
    if output_path == main_board:
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    donor = pcbnew.LoadBoard(str(donor_path))
    merge_button_hardware(board, donor)
    validate(board)
    pcbnew.SaveBoard(str(output_path), board)

    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded)
    print(
        f"Saved three-button PCB: {output_path}; "
        f"footprints={len(list(reloaded.GetFootprints()))}, nets={reloaded.GetNetCount()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
