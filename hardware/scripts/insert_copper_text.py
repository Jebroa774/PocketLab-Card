"""Insert explicit track/via S-expressions without pcbnew netcode remapping.

KiCad 10's Python SaveBoard currently remaps newly constructed connected-item
netcodes on this board.  This small helper keeps the authoritative PCB syntax
unchanged and inserts only well-formed copper records with named nets.  KiCad
CLI remains the parser, zone filler, and DRC authority for every candidate.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import uuid


def parse_point(value: str) -> tuple[float, float]:
    x_text, y_text = value.split(",", 1)
    return float(x_text), float(y_text)


def number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def segment(
    net_name: str,
    layer: str,
    width: float,
    start: tuple[float, float],
    end: tuple[float, float],
) -> str:
    return (
        "\t(segment\n"
        f"\t\t(start {number(start[0])} {number(start[1])})\n"
        f"\t\t(end {number(end[0])} {number(end[1])})\n"
        f"\t\t(width {number(width)})\n"
        "\t\t(locked yes)\n"
        f"\t\t(layer \"{layer}\")\n"
        f"\t\t(net \"{net_name}\")\n"
        f"\t\t(uuid \"{uuid.uuid4()}\")\n"
        "\t)\n"
    )


def via(net_name: str, kind: str, position: tuple[float, float]) -> str:
    if kind == "micro-f-in1":
        header, layers, diameter, drill = "via micro", '"F.Cu" "In1.Cu"', 0.30, 0.10
    elif kind == "micro-in2-b":
        header, layers, diameter, drill = "via micro", '"In2.Cu" "B.Cu"', 0.30, 0.10
    elif kind == "micro-in1-in2":
        header, layers, diameter, drill = "via micro", '"In1.Cu" "In2.Cu"', 0.30, 0.10
    elif kind == "through":
        header, layers, diameter, drill = "via", '"F.Cu" "B.Cu"', 0.45, 0.20
    else:
        raise RuntimeError(f"Unsupported via kind: {kind}")
    return (
        f"\t({header}\n"
        f"\t\t(at {number(position[0])} {number(position[1])})\n"
        f"\t\t(size {number(diameter)})\n"
        f"\t\t(drill {number(drill)})\n"
        f"\t\t(layers {layers})\n"
        "\t\t(locked yes)\n"
        f"\t\t(net \"{net_name}\")\n"
        f"\t\t(uuid \"{uuid.uuid4()}\")\n"
        "\t)\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", required=True)
    parser.add_argument("--layer", choices=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"), required=True)
    parser.add_argument("--point", action="append", type=parse_point, required=True)
    parser.add_argument("--width", type=float, default=0.20)
    parser.add_argument(
        "--endpoint-via",
        choices=("none", "micro-f-in1", "micro-in2-b", "micro-in1-in2", "through"),
        default="none",
    )
    parser.add_argument(
        "--via-point",
        action="append",
        type=lambda value: (value.split(":", 1)[0], parse_point(value.split(":", 1)[1])),
        default=[],
        metavar="KIND:X,Y",
        help="Insert an explicit via at one or more intermediate points",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        raise RuntimeError("Output must differ from input")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force: {output_path}")
    if len(args.point) < 2:
        raise RuntimeError("At least two --point values are required")

    records = []
    if args.endpoint_via != "none":
        records.append(via(args.net, args.endpoint_via, args.point[0]))
        records.append(via(args.net, args.endpoint_via, args.point[-1]))
    records.extend(via(args.net, kind, position) for kind, position in args.via_point)
    records.extend(
        segment(args.net, args.layer, args.width, start, end)
        for start, end in zip(args.point, args.point[1:])
        if start != end
    )

    text = input_path.read_text(encoding="utf-8")
    zone_at = text.find("\n\t(zone")
    search_end = zone_at if zone_at >= 0 else len(text)
    net_marker = f'\n\t\t(net "{args.net}")'
    net_at = text.rfind(net_marker, 0, search_end)
    insertion = text.find("\n\t)", net_at, search_end) + len("\n\t)") if net_at >= 0 else -1
    if insertion < len("\n\t)"):
        insertion = zone_at
    if insertion < 0:
        insertion = text.rfind("\n)")
    if insertion < 0:
        raise RuntimeError("Cannot locate a top-level PCB insertion point")
    text = text[:insertion] + "\n" + "".join(records) + text[insertion:]
    output_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Inserted copper: net={args.net}; records={len(records)}; output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
