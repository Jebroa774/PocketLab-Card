"""Flip TP105 to the back and place it on the existing VBUS_USB trunk."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


EXPECTED_POSITION_MM = (57.547277, 22.346000)
TARGET_POSITION_MM = (99.000000, 50.400000)


def xy(position: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def point(position: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(position[0]), pcbnew.FromMM(position[1]))


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
        raise RuntimeError("Refusing to overwrite the authoritative PCB directly")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    board = pcbnew.LoadBoard(str(input_path))
    testpoint = board.FindFootprintByReference("TP105")
    if testpoint is None:
        raise RuntimeError("Missing TP105")
    current = xy(testpoint.GetPosition())
    at_expected = all(abs(a - b) <= 0.001 for a, b in zip(current, EXPECTED_POSITION_MM))
    at_target = all(abs(a - b) <= 0.001 for a, b in zip(current, TARGET_POSITION_MM))
    if not (at_expected or at_target):
        raise RuntimeError(f"Unexpected TP105 position: {current}")
    pads = list(testpoint.Pads())
    if len(pads) != 1 or pads[0].GetNetname() != "/VBUS_USB":
        raise RuntimeError("Unexpected TP105 pad assignment")
    if at_expected and testpoint.GetLayer() != pcbnew.F_Cu:
        raise RuntimeError("Expected TP105 to start on F.Cu")
    if at_target and testpoint.GetLayer() != pcbnew.B_Cu:
        raise RuntimeError("Expected placed TP105 to be on B.Cu")

    if at_expected:
        testpoint.Flip(testpoint.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        testpoint.SetPosition(point(TARGET_POSITION_MM))
    testpoint.SetLocked(True)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(f"Saved TP105 VBUS_USB candidate: {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
