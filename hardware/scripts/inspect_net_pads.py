"""Print absolute footprint-pad positions for one PCB net.

The helper intentionally avoids iterating board tracks; KiCad 10 SWIG track
iteration can be very slow on this large routed board.  It is a read-only
diagnostic used when an unrouted DRC group is represented by a track endpoint.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew

from route_plane_fanouts import item_key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--net", help="Net name; omit to inspect every pad")
    parser.add_argument("--bounds", help="xmin,ymin,xmax,ymax")
    parser.add_argument(
        "--show-groups",
        action="store_true",
        help="append the KiCad connectivity-group number for each pad",
    )
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
    board = pcbnew.LoadBoard(str(args.input.resolve()))
    if args.show_groups:
        board.BuildConnectivity()
    group_ids: dict[frozenset[str], int] = {}
    rows: list[tuple[float, float, str, str, str, str, int]] = []
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            if net_name is not None and pad.GetNetname() != net_name:
                continue
            position = pad.GetPosition()
            x = pcbnew.ToMM(position.x)
            y = pcbnew.ToMM(position.y)
            if bounds and not (
                bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]
            ):
                continue
            rows.append(
                (
                    x,
                    y,
                    footprint.GetReference(),
                    pad.GetNumber(),
                    board.GetLayerName(pad.GetLayer()),
                    pad.GetNetname(),
                    group_ids.setdefault(
                        frozenset(
                            item_key(item)
                            for item in board.GetConnectivity().GetConnectedItems(pad)
                        ),
                        len(group_ids) + 1,
                    )
                    if args.show_groups
                    else 0,
                )
            )
    for x, y, reference, number, layer, pad_net, group_id in sorted(rows):
        suffix = f"\tgroup={group_id}" if args.show_groups else ""
        print(f"{reference}.{number}\t{x:.6f},{y:.6f}\t{layer}\t{pad_net}{suffix}")
    print(f"pads={len(rows)} net={net_name or '*'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
