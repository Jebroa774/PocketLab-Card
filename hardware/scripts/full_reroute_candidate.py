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
    parser.add_argument(
        "--selection-strategy",
        choices=("sequential", "random", "prioritized"),
        default="prioritized",
    )
    parser.add_argument(
        "--optimizer",
        action="store_true",
        help="enable FreeRouting's post-routing optimization stage",
    )
    parser.add_argument(
        "--updating-strategy",
        choices=("greedy", "global", "hybrid"),
        default="greedy",
        help="optimizer update strategy",
    )
    parser.add_argument(
        "--hybrid-ratio",
        default="1:1",
        help="global:greedy pass ratio used with --updating-strategy hybrid",
    )
    parser.add_argument(
        "--optimizer-max-passes",
        type=int,
        default=1,
        help="maximum number of complete optimizer sweeps",
    )
    parser.add_argument(
        "--optimizer-max-items",
        type=int,
        default=200,
        help="maximum number of optimizer item attempts",
    )
    parser.add_argument(
        "--optimizer-max-consecutive-failures",
        type=int,
        default=80,
        help="stop an optimizer sweep after this many consecutive failed attempts",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Stop after this many autorouter item attempts and save the partial result",
    )
    parser.add_argument("--keep-existing", action="store_true")
    parser.add_argument("--in1-signal", action="store_true")
    parser.add_argument("--keep-in1-zones", action="store_true")
    parser.add_argument("--in2-signal", action="store_true")
    parser.add_argument("--keep-in2-zones", action="store_true")
    parser.add_argument("--make-existing-routable", action="store_true")
    parser.add_argument(
        "--remove-all-zones",
        action="store_true",
        help="remove copper-pour zones while preserving rule-area keepouts",
    )
    parser.add_argument(
        "--strict-drc",
        action="store_true",
        help="Make FreeRouting reject clearance/collision violations while routing",
    )
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()

    protected = {args.input.resolve()}
    destinations = (args.stripped, args.dsn, args.ses, args.output)
    if any(path.resolve() in protected for path in destinations):
        raise RuntimeError("Every output must be separate from the input board")
    if (
        args.passes < 1
        or args.threads < 1
        or args.optimizer_max_passes < 1
        or args.optimizer_max_items < 1
        or args.optimizer_max_consecutive_failures < 1
    ):
        raise RuntimeError("pass, thread, item and failure limits must be positive")

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    removed_zones = 0
    if args.remove_all_zones:
        for zone in list(board.Zones()):
            if not zone.GetIsRuleArea():
                board.Delete(zone)
                removed_zones += 1
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
        f"--router.strict_drc={'true' if args.strict_drc else 'false'}",
        "--router.copper_to_edge_clearance_um=500",
        "--router.fanout.enabled=false",
        f"--router.optimizer.enabled={'true' if args.optimizer else 'false'}",
        f"--router.optimizer.max_passes={args.optimizer_max_passes}",
        f"--router.optimizer.max_items={args.optimizer_max_items}",
        "--router.optimizer.max_consecutive_failures="
        f"{args.optimizer_max_consecutive_failures}",
        "--router.automatic_neckdown=true",
        "-de",
        str(args.dsn.resolve()),
        "-do",
        str(args.ses.resolve()),
        "-mp",
        str(args.passes),
        "-mt",
        str(args.threads),
        "-is",
        args.selection_strategy,
        "-us",
        args.updating_strategy,
        "-l",
        "en",
    ]
    if args.updating_strategy == "hybrid":
        ratio_parts = args.hybrid_ratio.split(":")
        if (
            len(ratio_parts) != 2
            or not all(part.isdigit() and int(part) > 0 for part in ratio_parts)
        ):
            raise RuntimeError("hybrid-ratio must be two positive integers, e.g. 1:1")
        command.extend(("-hr", args.hybrid_ratio))
    if args.max_items is not None:
        if args.max_items < 1:
            raise RuntimeError("max-items must be positive")
        command.insert(5, f"--router.max_items={args.max_items}")
        command.insert(6, "--router.save_intermediate_stages=true")
    print("Starting full FreeRouting run", flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"FreeRouting failed with exit code {completed.returncode}")
    if not args.ses.is_file() or args.ses.stat().st_size < 100:
        raise RuntimeError("FreeRouting did not create a usable SES")

    # When existing routes were made routable, the SES contains their complete
    # replacement geometry.  Remove the pre-export track objects first so the
    # import does not duplicate every via and segment.
    removed_before_import = 0
    if args.make_existing_routable:
        removed_before_import = len(list(board.GetTracks()))
        for item in list(board.GetTracks()):
            board.Delete(item)
    if not pcbnew.ImportSpecctraSES(board, str(args.ses.resolve())):
        raise RuntimeError("KiCad SES import failed")
    normalized_vias = 0
    minimum_ring_mm = 0.10
    for item in board.GetTracks():
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        diameter_mm = pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu))
        drill_mm = pcbnew.ToMM(item.GetDrillValue())
        maximum_drill_mm = diameter_mm - 2.0 * minimum_ring_mm
        if drill_mm > maximum_drill_mm + 1e-9:
            item.SetDrill(pcbnew.FromMM(maximum_drill_mm))
            normalized_vias += 1
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
        f"reload_opens={reload_opens}, removed_before_import={removed_before_import}, "
        f"normalized_vias={normalized_vias}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
