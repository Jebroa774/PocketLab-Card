"""Mark known duplicated physical terminals as internally commoned."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


SWITCH_REFS = frozenset({"SW1", "SW2", "SW3", "SW4", "SW6", "SW7"})
SHELL_REFS = frozenset({"J1", "J2"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    main_board = Path(__file__).resolve().parent.parent / "PocketLab-Card.kicad_pcb"
    if output_path == main_board.resolve():
        raise RuntimeError("Refusing to overwrite the main PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    found: set[str] = set()
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if reference not in SWITCH_REFS | SHELL_REFS:
            continue
        pad_numbers = [pad.GetNumber() for pad in footprint.Pads()]
        if reference in SWITCH_REFS and sorted(pad_numbers) != ["1", "1", "2", "2"]:
            raise RuntimeError(f"Unexpected switch terminals on {reference}: {pad_numbers}")
        if reference in SHELL_REFS and pad_numbers.count("SH") != 4:
            raise RuntimeError(f"Unexpected shell terminals on {reference}: {pad_numbers}")
        footprint.SetDuplicatePadNumbersAreJumpers(True)
        found.add(reference)
    expected = SWITCH_REFS | SHELL_REFS
    if found != expected:
        raise RuntimeError(f"Missing internally commoned footprints: {sorted(expected - found)}")

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    print(f"Saved internal-switch-jumper candidate: {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
