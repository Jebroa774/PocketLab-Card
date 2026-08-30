"""Add one explicitly reviewed local migration link to a PCB candidate.

The helper is deliberately small and refuses to overwrite the authoritative
board.  It is used for short links between retained legacy copper and a
smaller factory-assembly pad after the footprint centre was preserved.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import uuid

import pcbnew


LAYERS = {
    "F.Cu": pcbnew.F_Cu,
    "B.Cu": pcbnew.B_Cu,
    "In1.Cu": pcbnew.In1_Cu,
    "In2.Cu": pcbnew.In2_Cu,
}


def point(value: str) -> tuple[float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("points must use x,y")
    return float(parts[0]), float(parts[1])


def vector(value: tuple[float, float]) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(value[0]), pcbnew.FromMM(value[1]))


def main() -> int:
    hardware_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument("--layer", choices=LAYERS, default="F.Cu")
    parser.add_argument("--width", type=float, default=0.15)
    parser.add_argument("--point", type=point, action="append", default=[])
    parser.add_argument("--via", type=point, action="append", default=[])
    parser.add_argument("--via-size", type=float, default=0.45)
    parser.add_argument("--via-drill", type=float, default=0.20)
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Insert native segment blocks without refilling/saving the board",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if len(args.point) == 1 or (not args.point and not args.via):
        raise RuntimeError("Provide either zero or at least two points, and/or a via")
    output_path = args.output.resolve()
    if output_path == (hardware_dir / "PocketLab-Card.kicad_pcb").resolve():
        raise RuntimeError("Refusing to overwrite the authoritative PCB")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")

    net_name = args.net if args.net.startswith("/") else f"/{args.net}"
    if args.text_only:
        input_text = args.input.resolve().read_text(encoding="utf-8")
        if f'(net "{net_name}")' not in input_text:
            raise RuntimeError(f"Net is missing: {net_name}")
        segments = []
        for start, end in zip(args.point, args.point[1:]):
            segments.append(
                "\t(segment\n"
                f"\t\t(start {start[0]:.6f} {start[1]:.6f})\n"
                f"\t\t(end {end[0]:.6f} {end[1]:.6f})\n"
                f"\t\t(width {args.width:.6f})\n"
                "\t\t(locked yes)\n"
                f"\t\t(layer \"{args.layer}\")\n"
                f"\t\t(net \"{net_name}\")\n"
                f"\t\t(uuid \"{uuid.uuid4()}\")\n"
                "\t)\n"
            )
        for at in args.via:
            segments.append(
                "\t(via\n"
                f"\t\t(at {at[0]:.6f} {at[1]:.6f})\n"
                f"\t\t(size {args.via_size:.6f})\n"
                f"\t\t(drill {args.via_drill:.6f})\n"
                "\t\t(layers \"F.Cu\" \"B.Cu\")\n"
                "\t\t(locked yes)\n"
                f"\t\t(net \"{net_name}\")\n"
                f"\t\t(uuid \"{uuid.uuid4()}\")\n"
                "\t)\n"
            )
        insertion = input_text.find("\n\t(zone\n")
        if insertion < 0:
            insertion = input_text.rfind("\n)")
        output_path.write_text(
            input_text[:insertion] + "\n" + "".join(segments) + input_text[insertion:],
            encoding="utf-8",
            newline="\n",
        )
        for suffix in (".kicad_pro", ".kicad_dru"):
            shutil.copyfile(
                hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix)
            )
        print(
            f"Added {max(0, len(args.point) - 1)} {net_name} native segment(s) on "
            f"{args.layer} at {args.width:.3f} mm and {len(args.via)} via(s)"
        )
        return 0

    board = pcbnew.LoadBoard(str(args.input.resolve()))
    net = board.FindNet(net_name)
    if net is None:
        raise RuntimeError(f"Net is missing: {net_name}")
    for start, end in zip(args.point, args.point[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(vector(start))
        track.SetEnd(vector(end))
        track.SetWidth(pcbnew.FromMM(args.width))
        track.SetLayer(LAYERS[args.layer])
        track.SetNet(net)
        track.SetLocked(True)
        board.Add(track)
    for at in args.via:
        via_item = pcbnew.PCB_VIA(board)
        via_item.SetPosition(vector(at))
        via_item.SetWidth(pcbnew.FromMM(args.via_size))
        via_item.SetDrill(pcbnew.FromMM(args.via_drill))
        via_item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via_item.SetNet(net)
        via_item.SetLocked(True)
        board.Add(via_item)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    for suffix in (".kicad_pro", ".kicad_dru"):
        shutil.copyfile(hardware_dir / f"PocketLab-Card{suffix}", output_path.with_suffix(suffix))
    print(
        f"Added {max(0, len(args.point) - 1)} {net_name} segment(s) on {args.layer} "
        f"at {args.width:.3f} mm and {len(args.via)} via(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
