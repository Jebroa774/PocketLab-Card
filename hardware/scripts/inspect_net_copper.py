"""Print native segment/via geometry for one PCB net without SWIG tracks."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from restore_baseline_net import copper_blocks


POINT_RE = re.compile(r"\((start|end|at)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")
LAYER_RE = re.compile(r'\(layer "([^"]+)"\)|\(layers "([^"]+)" "([^"]+)"\)')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--net", help="Net name; omit to inspect every net")
    parser.add_argument("--bounds", help="xmin,ymin,xmax,ymax")
    args = parser.parse_args()
    net_name = None
    if args.net:
        net_name = args.net if args.net.startswith("/") else f"/{args.net}"
    bounds = None
    if args.bounds:
        values = [float(value) for value in args.bounds.split(",")]
        if len(values) != 4:
            raise RuntimeError("bounds must be xmin,ymin,xmax,ymax")
        bounds = tuple(values)
    text = args.input.resolve().read_text(encoding="utf-8")
    count = 0
    for start, end, kind, item_uuid, block_net in copper_blocks(text):
        if net_name is not None and block_net != net_name:
            continue
        block = text[start:end]
        points = [(float(x), float(y)) for _name, x, y in POINT_RE.findall(block)]
        if bounds and not any(
            bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]
            for x, y in points
        ):
            continue
        layer_match = LAYER_RE.search(block)
        layers = "/".join(value for value in layer_match.groups() if value) if layer_match else "?"
        coordinates = " -> ".join(f"{x:.6f},{y:.6f}" for x, y in points)
        print(f"{kind}\t{coordinates}\t{layers}\t{block_net}\t{item_uuid}")
        count += 1
    print(f"items={count} net={net_name or '*'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
