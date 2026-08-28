"""Merge linear Specctra wire fragments and remove exact duplicate vias.

KiCad exports every PCB segment as an individual Specctra wire.  On dense boards,
Freerouting can spend minutes repeatedly splitting and recombining those fragments
before it starts the actual autorouter.  This helper keeps the copper geometry and
net assignments unchanged while joining only unambiguous, degree-two chains that
share layer, width, net, and route type.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import re


ATOM = r'(?:"(?:[^"\\]|\\.)*"|[^()\s]+)'
WIRE_RE = re.compile(
    rf"^(?P<indent>\s*)\(wire\s+\(path\s+(?P<layer>{ATOM})\s+"
    rf"(?P<width>{ATOM})\s+(?P<coords>.*?)\)\s*"
    rf"\(net\s+(?P<net>{ATOM})\)\s*\(type\s+(?P<type>{ATOM})\)\)\s*$"
)
VIA_RE = re.compile(
    rf"^(?P<indent>\s*)\(via\s+(?P<padstack>{ATOM})\s+"
    rf"(?P<x>{ATOM})\s+(?P<y>{ATOM})\s+\(net\s+(?P<net>{ATOM})\)\s*"
    rf"\(type\s+(?P<type>{ATOM})\)\)\s*$"
)


Point = tuple[str, str]


@dataclass
class Wire:
    indent: str
    layer: str
    width: str
    points: list[Point]
    net: str
    route_type: str
    first_index: int

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.layer, self.width, self.net, self.route_type

    @property
    def endpoints(self) -> tuple[Point, Point]:
        return self.points[0], self.points[-1]

    def render(self) -> str:
        coords = "  ".join(f"{x} {y}" for x, y in self.points)
        return (
            f"{self.indent}(wire (path {self.layer} {self.width}  {coords})"
            f"(net {self.net})(type {self.route_type}))\n"
        )


def parse_wire(line: str, index: int) -> Wire | None:
    match = WIRE_RE.match(line.rstrip("\r\n"))
    if not match:
        return None
    tokens = match.group("coords").split()
    if len(tokens) < 4 or len(tokens) % 2:
        raise RuntimeError(f"Invalid wire coordinates on line {index + 1}")
    points = list(zip(tokens[0::2], tokens[1::2], strict=True))
    return Wire(
        indent=match.group("indent"),
        layer=match.group("layer"),
        width=match.group("width"),
        points=points,
        net=match.group("net"),
        route_type=match.group("type"),
        first_index=index,
    )


def canonical_points(points: list[Point]) -> tuple[Point, ...]:
    forward = tuple(points)
    reverse = tuple(reversed(points))
    return min(forward, reverse)


def merge_group(
    wires: list[Wire], protected_points: frozenset[Point]
) -> tuple[list[Wire], int, int]:
    unique: list[Wire] = []
    seen: set[tuple[Point, ...]] = set()
    duplicates = 0
    for wire in wires:
        signature = canonical_points(wire.points)
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        unique.append(wire)

    active: dict[int, Wire] = {index: wire for index, wire in enumerate(unique)}
    endpoints: dict[Point, set[int]] = defaultdict(set)
    for wire_id, wire in active.items():
        start, end = wire.endpoints
        endpoints[start].add(wire_id)
        endpoints[end].add(wire_id)

    candidates = deque(point for point, ids in endpoints.items() if len(ids) == 2)
    next_id = len(active)
    merges = 0
    while candidates:
        point = candidates.popleft()
        if point in protected_points:
            continue
        ids = endpoints.get(point, set())
        if len(ids) != 2:
            continue
        first_id, second_id = tuple(ids)
        first = active.get(first_id)
        second = active.get(second_id)
        if first is None or second is None:
            continue
        if first.points[0] == first.points[-1] or second.points[0] == second.points[-1]:
            continue
        shared = set(first.endpoints) & set(second.endpoints)
        if shared != {point}:
            continue

        first_points = (
            first.points if first.points[-1] == point else list(reversed(first.points))
        )
        second_points = (
            second.points if second.points[0] == point else list(reversed(second.points))
        )
        joined = Wire(
            indent=first.indent,
            layer=first.layer,
            width=first.width,
            points=first_points + second_points[1:],
            net=first.net,
            route_type=first.route_type,
            first_index=min(first.first_index, second.first_index),
        )

        affected = set(first.endpoints + second.endpoints)
        for old_id, old_wire in ((first_id, first), (second_id, second)):
            del active[old_id]
            for endpoint in old_wire.endpoints:
                endpoints[endpoint].discard(old_id)
                if not endpoints[endpoint]:
                    del endpoints[endpoint]

        joined_id = next_id
        next_id += 1
        active[joined_id] = joined
        for endpoint in joined.endpoints:
            endpoints[endpoint].add(joined_id)
            affected.add(endpoint)
        for endpoint in affected:
            if len(endpoints.get(endpoint, set())) == 2:
                candidates.append(endpoint)
        merges += 1

    return list(active.values()), merges, duplicates


def dsn_coordinate(nanometres: int, invert: bool = False) -> str:
    value = Decimal(nanometres) / Decimal(1000)
    if invert:
        value = -value
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--board",
        type=Path,
        help="KiCad board whose pad positions must remain wire endpoints",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = args.input.resolve()
    destination = args.output.resolve()
    if not source.is_file():
        raise RuntimeError(f"Input DSN does not exist: {source}")
    if source == destination:
        raise RuntimeError("Output must be separate from input")
    if destination.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {destination}")

    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    protected_points: set[Point] = set()
    for line in lines:
        via = VIA_RE.match(line.rstrip("\r\n"))
        if via:
            protected_points.add((via.group("x"), via.group("y")))
    if args.board is not None:
        import pcbnew

        board_path = args.board.resolve()
        if not board_path.is_file():
            raise RuntimeError(f"Board does not exist: {board_path}")
        board = pcbnew.LoadBoard(str(board_path))
        for footprint in board.GetFootprints():
            for pad in footprint.Pads():
                position = pad.GetPosition()
                protected_points.add(
                    (
                        dsn_coordinate(position.x),
                        dsn_coordinate(position.y, invert=True),
                    )
                )
    grouped: dict[tuple[str, str, str, str], list[Wire]] = defaultdict(list)
    wire_indices: set[int] = set()
    for index, line in enumerate(lines):
        wire = parse_wire(line, index)
        if wire is not None:
            grouped[wire.key].append(wire)
            wire_indices.add(index)

    replacements: dict[int, list[str]] = defaultdict(list)
    merges = 0
    duplicate_wires = 0
    output_wires = 0
    for wires in grouped.values():
        merged, group_merges, group_duplicates = merge_group(
            wires, frozenset(protected_points)
        )
        merges += group_merges
        duplicate_wires += group_duplicates
        output_wires += len(merged)
        for wire in sorted(merged, key=lambda item: item.first_index):
            replacements[wire.first_index].append(wire.render())

    seen_vias: set[tuple[str, str, str, str, str]] = set()
    duplicate_vias = 0
    result: list[str] = []
    for index, line in enumerate(lines):
        if index in wire_indices:
            result.extend(replacements.get(index, []))
            continue
        via = VIA_RE.match(line.rstrip("\r\n"))
        if via:
            signature = (
                via.group("padstack"),
                via.group("x"),
                via.group("y"),
                via.group("net"),
                via.group("type"),
            )
            if signature in seen_vias:
                duplicate_vias += 1
                continue
            seen_vias.add(signature)
        result.append(line)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(result), encoding="utf-8", newline="\n")
    print(
        f"Normalized DSN: wires {len(wire_indices)}->{output_wires}; "
        f"merges={merges}; duplicate_wires={duplicate_wires}; "
        f"duplicate_vias={duplicate_vias}; protected_points={len(protected_points)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
