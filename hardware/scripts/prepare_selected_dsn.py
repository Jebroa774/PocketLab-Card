"""Reduce a guarded Specctra DSN to an explicitly selected net batch."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from route_pcb import dsn_atom, dsn_expression_end


def normalize(name: str) -> str:
    return name if name.startswith("/") else f"/{name}"


def quote_atom(value: str) -> str:
    if value and not any(character.isspace() or character in '()"' for character in value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_class(
    name: str, members: set[str], source: str, rule_start: int, child_end: int, indent: str
) -> str:
    return (
        f"(class {quote_atom(name)} "
        + " ".join(quote_atom(member) for member in sorted(members))
        + "\n"
        + indent
        + "  "
        + source[rule_start:child_end]
    )


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


def stub_net_expression(source: str, start: int, end: int, name: str) -> str:
    pins_match = re.search(r"\(pins\s+", source[start:end])
    if not pins_match:
        return source[start:end]
    pins_offset = start + pins_match.end()
    first_pin, _ = dsn_atom(source, pins_offset)
    indent_start = source.rfind("\n", 0, start) + 1
    indent = source[indent_start:start]
    return (
        f"(net {quote_atom(name)}\n"
        f"{indent}  (pins {quote_atom(first_pin)})\n"
        f"{indent})"
    )


def select_network(
    source: str, selected: frozenset[str], stub_unselected: bool = False
) -> str:
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
    assigned: set[str] = set()
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
            elif stub_unselected:
                pieces.append(
                    stub_net_expression(source, child_start, child_end, child_name)
                )
        elif child_head == "class":
            rule_start = first_child_expression(source, after_name, child_end)
            member_offset = after_name
            members: set[str] = set()
            while member_offset < rule_start:
                while member_offset < rule_start and source[member_offset].isspace():
                    member_offset += 1
                if member_offset >= rule_start:
                    break
                member, member_offset = dsn_atom(source, member_offset)
                members.add(member)
            retained = selected & members
            if stub_unselected:
                assigned.update(retained)
                pieces.append(source[child_start:child_end])
                copy_from = child_end
                cursor = child_end
                continue
            if not retained:
                copy_from = child_end
                cursor = child_end
                continue
            assigned.update(retained)
            indent_start = source.rfind("\n", 0, child_start) + 1
            indent = source[indent_start:child_start]
            pieces.append(
                f"(class {quote_atom(child_name)} "
                + " ".join(quote_atom(member) for member in sorted(retained))
                + "\n"
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
    unassigned = selected - assigned
    if unassigned:
        raise RuntimeError(f"Selected nets have no netclass: {sorted(unassigned)}")
    result = "".join(pieces)
    reduced = result[network_start:dsn_expression_end(result, network_start)]
    declared = set(re.findall(r"(?m)^\s*\(net\s+(\S+)", reduced))
    if stub_unselected:
        if not selected <= declared:
            raise RuntimeError(
                f"Stubbed DSN is missing selected declarations: {selected - declared}"
            )
    elif declared != selected:
        raise RuntimeError(f"Reduced DSN declaration mismatch: {declared} != {selected}")
    return result


def split_network_classes(
    source: str, selected: frozenset[str]
) -> tuple[str, tuple[str, ...]]:
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
    assigned: set[str] = set()
    ignored_classes: list[str] = []
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
            pieces.append(source[child_start:child_end])
            if child_name in selected:
                seen.add(child_name)
        elif child_head == "class":
            rule_start = first_child_expression(source, after_name, child_end)
            member_offset = after_name
            members: set[str] = set()
            while member_offset < rule_start:
                while member_offset < rule_start and source[member_offset].isspace():
                    member_offset += 1
                if member_offset >= rule_start:
                    break
                member, member_offset = dsn_atom(source, member_offset)
                members.add(member)
            routed = selected & members
            ignored = members - selected
            indent_start = source.rfind("\n", 0, child_start) + 1
            indent = source[indent_start:child_start]
            class_pieces: list[str] = []
            if routed:
                assigned.update(routed)
                class_pieces.append(
                    render_class(
                        f"SELECT_{child_name}", routed, source, rule_start, child_end, indent
                    )
                )
            if ignored:
                ignored_name = f"IGNORE_{child_name}"
                ignored_classes.append(ignored_name)
                class_pieces.append(
                    render_class(
                        ignored_name, ignored, source, rule_start, child_end, indent
                    )
                )
            pieces.append(("\n" + indent).join(class_pieces))
        else:
            pieces.append(source[child_start:child_end])
        copy_from = child_end
        cursor = child_end
    pieces.append(source[copy_from:])
    missing = selected - seen
    if missing:
        raise RuntimeError(f"Selected nets are absent from DSN: {sorted(missing)}")
    unassigned = selected - assigned
    if unassigned:
        raise RuntimeError(f"Selected nets have no netclass: {sorted(unassigned)}")
    return "".join(pieces), tuple(ignored_classes)


def promote_selected_wiring(source: str, selected: frozenset[str]) -> tuple[str, int]:
    matches = list(re.finditer(r"(?m)^\s*\(wiring\b", source))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one wiring section, found {len(matches)}")
    wiring_start = source.find("(", matches[0].start())
    wiring_end = dsn_expression_end(source, wiring_start)
    head, cursor = dsn_atom(source, wiring_start + 1)
    if head != "wiring":
        raise RuntimeError(f"Expected wiring expression, got {head!r}")

    pieces = [source[:cursor]]
    copy_from = cursor
    promoted = 0
    while cursor < wiring_end - 1:
        while cursor < wiring_end - 1 and source[cursor].isspace():
            cursor += 1
        if cursor >= wiring_end - 1:
            break
        child_start = cursor
        child_end = dsn_expression_end(source, child_start)
        child = source[child_start:child_end]
        net_match = re.search(r"\(net\s+", child)
        pieces.append(source[copy_from:child_start])
        if net_match:
            net_name, _ = dsn_atom(child, net_match.end())
            child = child.replace("(type route)", "(type fix)")
            if net_name in selected:
                count = child.count("(type fix)")
                child = child.replace("(type fix)", "(type route)")
                promoted += count
        pieces.append(child)
        copy_from = child_end
        cursor = child_end
    pieces.append(source[copy_from:])
    return "".join(pieces), promoted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", action="append", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--make-selected-routable", action="store_true")
    parser.add_argument("--stub-unselected", action="store_true")
    parser.add_argument("--split-classes", action="store_true")
    args = parser.parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if not input_path.is_file():
        raise RuntimeError(f"Input DSN does not exist: {input_path}")
    if output_path.exists() and not args.force:
        raise RuntimeError(f"Output exists; use --force to replace it: {output_path}")
    if args.stub_unselected and args.split_classes:
        raise RuntimeError("Choose either --stub-unselected or --split-classes")
    selected = frozenset(normalize(name) for name in args.net)
    ignored_classes: tuple[str, ...] = ()
    source = input_path.read_text(encoding="utf-8")
    if args.split_classes:
        result, ignored_classes = split_network_classes(source, selected)
    else:
        result = select_network(source, selected, args.stub_unselected)
    promoted = 0
    if args.make_selected_routable:
        result, promoted = promote_selected_wiring(result, selected)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8", newline="\n")
    print(
        f"Saved selected-net DSN: {output_path}; nets={len(selected)}; "
        f"promoted={promoted}; ignore_classes={','.join(ignored_classes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
