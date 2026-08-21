"""Create a full FreeRouting candidate without touching the main PCB."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

import pcbnew


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--stripped", type=Path, required=True)
    parser.add_argument("--dsn", type=Path, required=True)
    parser.add_argument("--ses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--passes", type=int, default=40)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--in1-signal", action="store_true")
    parser.add_argument("--keep-in1-zones", action="store_true")
    parser.add_argument("--in2-signal", action="store_true")
    parser.add_argument("--keep-in2-zones", action="store_true")
    parser.add_argument("--make-existing-routable", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()

    protected = {args.input.resolve()}
    destinations = (args.stripped, args.dsn, args.ses, args.output)
    if any(path.resolve() in protected for path in destinations):
        raise RuntimeError("Every output must be separate from the input board")
    if args.passes < 1 or args.threads < 1:
        raise RuntimeError("passes and threads must be positive")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    removed_zones = 0
    if args.in1_signal:
        board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_SIGNAL)
        board.SetLayerName(pcbnew.In1_Cu, "In1.Cu")
        if not args.keep_in1_zones:
            for zone in list(board.Zones()):
                if zone.GetLayer() == pcbnew.In1_Cu:
                    board.Delete(zone)
                    removed_zones += 1
    if args.in2_signal:
        board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_SIGNAL)
        board.SetLayerName(pcbnew.In2_Cu, "In2.Cu")
        if not args.keep_in2_zones:
            for zone in list(board.Zones()):
                if zone.GetLayer() == pcbnew.In2_Cu and zone.GetNetname() in {
                    "/+3V3",
                    "/+5V_AUX",
                    "/+5V_RAW",
                }:
                    board.Delete(zone)
                    removed_zones += 1
    removed = 0
    if not args.keep_existing:
        removed = len(list(board.GetTracks()))
        for item in list(board.GetTracks()):
            board.Delete(item)
    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    stripped_opens = int(connectivity.GetUnconnectedCount(False))
    if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
        raise RuntimeError("Could not refill zones after track removal")
    pcbnew.SaveBoard(str(args.stripped.resolve()), board)
    if not pcbnew.ExportSpecctraDSN(board, str(args.dsn.resolve())):
        raise RuntimeError("Specctra DSN export failed")
    promoted = 0
    if args.make_existing_routable:
        text = args.dsn.read_text(encoding="utf-8")
        promoted = text.count("(type fix)")
        args.dsn.write_text(
            text.replace("(type fix)", "(type route)"),
            encoding="utf-8",
            newline="\n",
        )
    print(
        f"Stripped candidate: removed={removed}, removed_zones={removed_zones}, "
        f"promoted={promoted}, opens={stripped_opens}",
        flush=True,
    )
    if args.export_only:
        return 0

    command = [
        str(args.java.resolve()),
        "-jar",
        str(args.jar.resolve()),
        "--gui.enabled=false",
        "--router.strict_drc=false",
        "--router.copper_to_edge_clearance_um=500",
        "--router.fanout.enabled=false",
        "--router.optimizer.enabled=false",
        "--router.automatic_neckdown=true",
        "-de",
        str(args.dsn.resolve()),
        "-do",
        str(args.ses.resolve()),
        "-mp",
        str(args.passes),
        "-mt",
        str(args.threads),
        "-l",
        "en",
    ]
    print("Starting full FreeRouting run", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"FreeRouting failed with exit code {completed.returncode}")
    if not args.ses.is_file() or args.ses.stat().st_size < 100:
        raise RuntimeError("FreeRouting did not create a usable SES")

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
        f"Full candidate saved: tracks={track_count}, opens={opens}, "
        f"reload_opens={reload_opens}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
