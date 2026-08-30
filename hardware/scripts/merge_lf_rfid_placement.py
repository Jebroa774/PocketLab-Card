"""Merge the reviewed via-free LF-RFID placement into the routed PCB.

``build_pcb.py`` remains the placement source of truth.  This helper copies
only the footprints that had to move for the LF analogue island and preserves
all unrelated footprints, zones, drawings and copper from the routed input.
Copper touching an old moved pad is removed before replacement so no hidden
stubs remain at the former component position.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


MOVED_FOOTPRINTS = (
    # Complete via-free HTRC110 analogue/resonance island.
    "U4",
    "R502",
    "C503",
    "C504",
    "C505",
    "C506",
    "C507",
    "C508",
    "C509",
    "R503",
    "R504",
    "TP502",
    # LF load switch/support moved to the front pocket vacated by U4.
    "U17",
    "R501",
    "C501",
    "C502",
    "R506",
    # Local collision-resolution moves required by the new LF island.
    "R608",
    "R611",
    "U24",
    "C706",
    "R514",
    "R515",
    "TP104",
    "TP105",
    "TP106",
    "TP107",
    "TP102",
    "TP301",
    "R204",
    "R718",
    "R730",
    "R731",
    "R732",
    "R733",
    "R734",
    "R605",
    "R606",
)

# These local routes cross footprints that change side/position.  Return the
# complete small branches to the ratsnest; the LF routing pass reconnects them
# after the placement merge instead of preserving hidden or dangling stubs.
CLEARED_NETS = frozenset(
    {
        "/IR_LED_A3",
        "/BOOT_N",
        "/BOARD_TEMP_HDR",
        "/I2C_SCL_HDR",
        "/IR_LED_K",
        "/SPI_MOSI_HDR",
        "/SPI_SCK_HDR",
        "/NFC_RESET_N",
        "/I2C_SDA",
        "/PAIR_N",
    }
)

SENSITIVE_LF_NETS = frozenset(
    {
        "/LF_TX1",
        "/LF_TX2",
        "/LF_ANT_A",
        "/LF_ANT_B",
        "/LF_TAP",
        "/LF_RX",
        "/LF_CEXT",
        "/LF_QGND",
        "/LF_CLK_4M",
    }
)


def get_or_add_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is not None:
        return net
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def remove_old_pad_copper(board: pcbnew.BOARD) -> tuple[int, set[str]]:
    """Delete track/via items that physically terminate in a moved pad."""

    old_pads = []
    for reference in MOVED_FOOTPRINTS:
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"Routed input is missing {reference}")
        old_pads.extend(footprint.Pads())

    removed = []
    for track in list(board.GetTracks()):
        if any(
            pad.GetNetname() == track.GetNetname()
            and (pad.HitTest(track.GetStart()) or pad.HitTest(track.GetEnd()))
            for pad in old_pads
        ):
            removed.append(track)

    removed_nets = {track.GetNetname() for track in removed}
    for track in removed:
        board.Delete(track)
    return len(removed), removed_nets


def replace_footprint(
    board: pcbnew.BOARD, donor: pcbnew.BOARD, reference: str
) -> None:
    source = donor.FindFootprintByReference(reference)
    existing = board.FindFootprintByReference(reference)
    if source is None or existing is None:
        raise RuntimeError(f"Input/donor footprint mismatch for {reference}")

    pad_nets = [pad.GetNetname() for pad in source.Pads()]
    board.Delete(existing)
    replacement = pcbnew.Cast_to_FOOTPRINT(source.Duplicate(False))
    board.Add(replacement)
    replacement.SetReference(reference)
    replacement_pads = list(replacement.Pads())
    if len(replacement_pads) != len(pad_nets):
        raise RuntimeError(f"Pad-count changed while duplicating {reference}")
    for pad, net_name in zip(replacement_pads, pad_nets, strict=True):
        pad.SetNet(get_or_add_net(board, net_name))


def merge_lf_placement(
    board: pcbnew.BOARD, donor: pcbnew.BOARD
) -> tuple[int, set[str]]:
    removed_count, removed_nets = remove_old_pad_copper(board)
    for track in list(board.GetTracks()):
        if track.GetNetname() in CLEARED_NETS:
            removed_nets.add(track.GetNetname())
            board.Delete(track)
            removed_count += 1
    for reference in MOVED_FOOTPRINTS:
        replace_footprint(board, donor, reference)
    return removed_count, removed_nets


def validate(board: pcbnew.BOARD, donor: pcbnew.BOARD) -> None:
    references = [footprint.GetReference() for footprint in board.GetFootprints()]
    if len(references) != 266 or len(references) != len(set(references)):
        raise RuntimeError(
            f"Expected 266 unique footprints after merge, got {len(references)}"
        )

    for reference in MOVED_FOOTPRINTS:
        actual = board.FindFootprintByReference(reference)
        expected = donor.FindFootprintByReference(reference)
        if actual is None or expected is None:
            raise RuntimeError(f"Merged/donor footprint mismatch for {reference}")
        if (
            actual.GetPosition() != expected.GetPosition()
            or actual.GetLayer() != expected.GetLayer()
            or abs(actual.GetOrientationDegrees() - expected.GetOrientationDegrees()) > 0.001
        ):
            raise RuntimeError(f"{reference} does not match the reviewed placement")

    analogue_refs = {
        "U4",
        "J3",
        "R502",
        "C503",
        "C504",
        "C505",
        "C506",
        "C507",
        "C508",
        "C509",
        "R503",
        "R504",
        "TP502",
        "Y501",
        "C513",
    }
    wrong_side = sorted(
        reference
        for reference in analogue_refs
        if board.FindFootprintByReference(reference).GetLayer() != pcbnew.B_Cu
    )
    if wrong_side:
        raise RuntimeError("LF analogue footprints are not all on B.Cu: " + ", ".join(wrong_side))

    forbidden_vias = sorted(
        {
            track.GetNetname()
            for track in board.GetTracks()
            if isinstance(track, pcbnew.PCB_VIA)
            and track.GetNetname() in SENSITIVE_LF_NETS
        }
    )
    if forbidden_vias:
        raise RuntimeError("Sensitive LF nets retained vias: " + ", ".join(forbidden_vias))


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
    removed_count, removed_nets = merge_lf_placement(board, donor)
    validate(board, donor)
    pcbnew.SaveBoard(str(output_path), board)

    reloaded = pcbnew.LoadBoard(str(output_path))
    validate(reloaded, donor)
    print(
        f"Saved LF-RFID placement PCB: {output_path}; "
        f"footprints={len(list(reloaded.GetFootprints()))}, "
        f"removed_pad_copper={removed_count}, "
        f"affected_nets={','.join(sorted(removed_nets))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
