"""Import a completed Specctra session into a separate KiCad board candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--ses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.output.resolve() == args.base.resolve():
        raise RuntimeError("Output must be separate from the base board")
    if not args.ses.is_file() or args.ses.stat().st_size < 100:
        raise RuntimeError("Specctra session is missing or empty")

    board = pcbnew.LoadBoard(str(args.base.resolve()))
    if not pcbnew.ImportSpecctraSES(board, str(args.ses.resolve())):
        raise RuntimeError("KiCad SES import failed")
    if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
        raise RuntimeError("Could not refill zones after SES import")

    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    opens = int(connectivity.GetUnconnectedCount(False))
    track_count = len(list(board.GetTracks()))
    pcbnew.SaveBoard(str(args.output.resolve()), board)

    reloaded = pcbnew.LoadBoard(str(args.output.resolve()))
    reloaded.BuildConnectivity()
    connectivity = reloaded.GetConnectivity()
    connectivity.RecalculateRatsnest()
    reload_opens = int(connectivity.GetUnconnectedCount(False))
    print(
        f"Candidate saved: tracks={track_count}, opens={opens}, "
        f"reload_opens={reload_opens}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
