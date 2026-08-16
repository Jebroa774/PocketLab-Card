"""Reduce a guarded Specctra DSN to an explicitly selected net batch."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from route_pcb import dsn_atom, dsn_expression_end


def normalize(name: str) -> str:
    return name if name.startswith("/") else f"/{name}"


def first_child_expression(text: str, start: int, end: int) -> int:
    quoted = False
    escaped = False
    for offset in range(start, end):
        character = text[offset]
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
        elif character == "(":
            return offset
    raise RuntimeError("Default class has no rule expressions")


def select_network(source: str, selected: frozenset[str]) -> str:
    matches = list(re.finditer(r"(?m)^\s*\(network\b", source))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one network section, found {len(matches)}")
    network_start = source.find("(", matches[0].start())
    network_end = dsn_expression_end(source, network_start)
    head, cursor = dsn_atom(source, network_start + 1)
    if head != "network":
        raise RuntimeError(f"Expected network expression, got {head!r}")

    pieces = [source[:cursor]]
    copy_from = cursor
    seen: set[str] = set()
    classes = 0
    while cursor < network_end - 1:
        while cursor < network_end - 1 and source[cursor].isspace():
            cursor += 1
        if cursor >= network_end - 1:
            break
        child_start = cursor
        child_end = dsn_expression_end(source, child_start)
        child_head, atom_offset = dsn_atom(source, child_start + 1)
        child_name, after_name = dsn_atom(source, atom_offset)
        pieces.append(source[copy_from:child_start])
        if child_head == "net":
            if child_name in selected:
                pieces.append(source[child_start:child_end])
                seen.add(child_name)
        elif child_head == "class":
            classes += 1
            if classes > 1:
                raise RuntimeError("Selected-net reducer expects one guarded default class")
            rule_start = first_child_expression(source, after_name, child_end)
            indent_start = source.rfind("\n", 0, child_start) + 1
            indent = source[indent_start:child_start]
            pieces.append(
                f"(class {child_name} {' '.join(sorted(selected))}\n"
                + indent
                + "  "
                + source[rule_start:child_end]
            )
        else:
            pieces.append(source[child_start:child_end])
        copy_from = child_end
        cursor = child_end
    pieces.append(source[copy_from:])
    missing = selected - seen
    if missing:
        raise RuntimeError(f"Selected nets are absent from guarded DSN: {sorted(missing)}")
    result = "".join(pieces)
    reduced = result[network_start:dsn_expression_end(result, network_start)]
    declared = set(re.findall(r"(?m)^\s*\(net\s+(\S+)", reduced))
    if declared != selected:
        raise RuntimeError(f"Reduced DSN declaration mismatch: {declared} != {selected}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", action="append", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input DSN does not exist: {input_path}")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")
    selected = frozenset(normalize(name) for name in args.net)
    result = select_network(input_path.read_text(encoding="utf-8"), selected)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8", newline="\n")
    print(f"Saved selected-net DSN: {output_path}; nets={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
