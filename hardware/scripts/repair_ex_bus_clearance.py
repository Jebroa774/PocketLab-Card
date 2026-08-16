"""Move the EX2_INT trunk away from the adjacent EX5_INT junction."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


OLD_UUID = "8a39bc7f-e440-43cc-b2db-5073a74e5307"
PATH = (
    (59.7100, 21.8200),
    (60.1500, 22.2600),
    (60.1500, 25.9400),
    (60.0250, 26.0657),
)


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


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

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    removed = False
    for track in board.GetTracks():
        if track.m_Uuid.AsString() == OLD_UUID:
            board.Remove(track)
            removed = True
            break
    if not removed:
        raise RuntimeError(f"Reviewed EX2_INT segment is missing: {OLD_UUID}")

    net = board.FindNet("/EX2_INT")
    if net is None:
        raise RuntimeError("/EX2_INT net is missing")
    for start, end in zip(PATH, PATH[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(0.20))
        track.SetLayer(pcbnew.B_Cu)
        track.SetNet(net)
        track.SetLocked(True)
        board.Add(track)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print("Replaced the EX2_INT/EX5_INT near-crossing with a 0.61-mm-centre corridor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
