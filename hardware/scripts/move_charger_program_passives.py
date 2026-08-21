"""Move the charger timer/termination resistors beside U5 and route them."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

import pcbnew


def point(x_mm: float, y_mm: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x_mm), pcbnew.FromMM(y_mm))


def footprint(board: pcbnew.BOARD, reference: str) -> pcbnew.FOOTPRINT:
    result = board.FindFootprintByReference(reference)
    if result is None:
        raise RuntimeError(f"Missing footprint: {reference}")
    return result


def pad(board: pcbnew.BOARD, reference: str, number: str) -> pcbnew.PAD:
    matches = [item for item in footprint(board, reference).Pads() if item.GetNumber() == number]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {reference}.{number}, got {len(matches)}")
    return matches[0]


def xy(item: pcbnew.BOARD_ITEM) -> tuple[float, float]:
    position = item.GetPosition()
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(*start))
    track.SetEnd(point(*end))
    track.SetWidth(pcbnew.FromMM(0.20))
    track.SetLayer(pcbnew.B_Cu)
    track.SetNet(board.FindNet(net_name))
    track.SetLocked(True)
    board.Add(track)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    hardware_dir = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    if output == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative board")
    if output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output}")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    placements = {
        "R114": (94.0, 47.6),
        "R112": (94.0, 53.3),
    }
    for reference, position in placements.items():
        item = footprint(board, reference)
        if item.GetLayer() != pcbnew.B_Cu:
            item.Flip(item.GetPosition(), False)
        item.SetOrientationDegrees(0.0)
        item.SetPosition(point(*position))

    routes = {
        "/CHG_TMR": (
            xy(pad(board, "U5", "14")),
            (92.15, 50.25),
            (92.60, 49.80),
            xy(pad(board, "R114", "1")),
        ),
        "/CHG_ITERM": (
            xy(pad(board, "U5", "15")),
            (92.15, 50.75),
            (92.60, 51.20),
            xy(pad(board, "R112", "1")),
        ),
    }
    for net_name, route in routes.items():
        for start, end in zip(route, route[1:]):
            add_track(board, net_name, start, end)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(
            hardware_dir / f"PocketLab-Card{suffix}", output.with_suffix(suffix)
        )
    print(f"MOVED charger passives: {placements}")
    for net_name, route in routes.items():
        print(f"ROUTED {net_name}: {route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
