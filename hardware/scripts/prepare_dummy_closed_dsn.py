"""Temporarily close non-selected ratsnest edges on a non-routable DSN layer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from prepare_selected_dsn import promote_selected_wiring, quote_atom
from route_pcb import dsn_atom, dsn_expression_end


DUMMY_PADSTACK = "DUMMY[0-3]_2:1_um"
PLANE_NETS = ("/GND", "/+3V3", "/+5V_AUX", "/+5V_RAW")


def normalize(name: str) -> str:
    return name if name.startswith("/") else f"/{name}"


def locate_expression(source: str, name: str) -> tuple[int, int, int]:
    matches = list(re.finditer(rf"(?m)^\s*\({re.escape(name)}\b", source))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {name} section, found {len(matches)}")
    start = source.find("(", matches[0].start())
    end = dsn_expression_end(source, start)
    head, cursor = dsn_atom(source, start + 1)
    if head != name:
        raise RuntimeError(f"Expected {name} expression, got {head!r}")
    return start, end, cursor


def dsn_coordinate(value: float) -> str:
    scaled = round(value * 1000.0, 3)
    if float(scaled).is_integer():
        return str(int(scaled))
    return f"{scaled:.3f}".rstrip("0").rstrip(".")


def parse_open_edges(report_path: Path) -> list[tuple[str, float, float, float, float]]:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    result: list[tuple[str, float, float, float, float]] = []
    for entry in report.get("unconnected_items", []):
        items = entry.get("items", [])
        if len(items) != 2:
            raise RuntimeError(f"Unexpected unconnected entry size: {len(items)}")
        names: list[str] = []
        for item in items:
            match = re.search(r"\[([^\]]+)\]", str(item.get("description", "")))
            if not match:
                raise RuntimeError(f"Cannot extract net from {item!r}")
            names.append(match.group(1))
        if names[0] != names[1]:
            raise RuntimeError(f"Mismatched unconnected nets: {names}")
        first = items[0]["pos"]
        second = items[1]["pos"]
        result.append(
            (
                names[0],
                float(first["x"]),
                float(first["y"]),
                float(second["x"]),
                float(second["y"]),
            )
        )
    return result


def pad_star_edges(
    board_path: Path, all_nets: bool
) -> list[tuple[str, float, float, float, float]]:
    import pcbnew

    board = pcbnew.LoadBoard(str(board_path.resolve()))
    pads_by_net: dict[str, list[tuple[float, float]]] = {net: [] for net in PLANE_NETS}
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            net = pad.GetNetname()
            if not net or (not all_nets and net not in pads_by_net):
                continue
            pads_by_net.setdefault(net, [])
            position = pad.GetPosition()
            pads_by_net[net].append(
                (pcbnew.ToMM(position.x), pcbnew.ToMM(position.y))
            )
    result: list[tuple[str, float, float, float, float]] = []
    for net, positions in pads_by_net.items():
        unique = sorted(set(positions))
        if len(unique) < 2:
            continue
        anchor_x, anchor_y = unique[0]
        result.extend(
            (net, anchor_x, anchor_y, x, y) for x, y in unique[1:]
        )
    return result


def insert_dummy_padstack(source: str) -> str:
    _, library_end, _ = locate_expression(source, "library")
    padstack = (
        f'    (padstack "{DUMMY_PADSTACK}"\n'
        "      (shape (circle F.Cu 2))\n"
        "      (shape (circle GND 2))\n"
        "      (shape (circle In2.Cu 2))\n"
        "      (shape (circle B.Cu 2))\n"
        "      (attach off)\n"
        "    )\n"
    )
    return source[: library_end - 1] + padstack + source[library_end - 1 :]


def insert_dummy_wiring(
    source: str,
    edges: list[tuple[str, float, float, float, float]],
    selected: frozenset[str],
) -> tuple[str, int, int]:
    _, _, wiring_cursor = locate_expression(source, "wiring")
    lines: list[str] = []
    vias: set[tuple[str, str, str]] = set()
    wire_count = 0
    for net, x1, y1, x2, y2 in edges:
        if net in selected:
            continue
        x1_text = dsn_coordinate(x1)
        y1_text = dsn_coordinate(-y1)
        x2_text = dsn_coordinate(x2)
        y2_text = dsn_coordinate(-y2)
        net_text = quote_atom(net)
        lines.append(
            f"    (wire (path GND 1  {x1_text} {y1_text}  {x2_text} {y2_text})"
            f"(net {net_text})(type fix))"
        )
        wire_count += 1
        vias.add((net, x1_text, y1_text))
        vias.add((net, x2_text, y2_text))
    for net, x_text, y_text in sorted(vias):
        lines.append(
            f'    (via "{DUMMY_PADSTACK}" {x_text} {y_text}'
            f"(net {quote_atom(net)})(type fix))"
        )
    insertion = "\n" + "\n".join(lines)
    return source[:wiring_cursor] + insertion + source[wiring_cursor:], wire_count, len(vias)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--drc", type=Path, required=True)
    parser.add_argument("--board", type=Path)
    parser.add_argument("--all-pad-stars", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", action="append", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {args.output}")
    selected = frozenset(normalize(name) for name in args.net)
    edges = parse_open_edges(args.drc.resolve())
    plane_edge_count = 0
    if args.board:
        plane_edges = pad_star_edges(args.board, args.all_pad_stars)
        plane_edge_count = len(plane_edges)
        edges.extend(plane_edges)
    available = {edge[0] for edge in edges}
    missing = selected - available
    if missing:
        raise RuntimeError(f"Selected nets have no open edges: {sorted(missing)}")

    source = args.input.read_text(encoding="utf-8")
    source = insert_dummy_padstack(source)
    source, wires, vias = insert_dummy_wiring(source, edges, selected)
    source, promoted = promote_selected_wiring(source, selected)
    args.output.write_text(source, encoding="utf-8", newline="\n")
    print(
        f"Saved dummy-closed DSN: selected={len(selected)}, dummy_wires={wires}, "
        f"dummy_vias={vias}, plane_edges={plane_edge_count}, promoted={promoted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
