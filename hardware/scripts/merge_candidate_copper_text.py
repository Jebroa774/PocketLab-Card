"""Merge selected new top-level segment/via S-expressions between PCB candidates."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


def expression_end(text: str, start: int) -> int:
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    raise RuntimeError("unterminated expression")


def copper_blocks(text: str):
    for match in re.finditer(r"(?m)^\t\((segment|via)\b", text):
        start = match.start() + 1
        end = expression_end(text, start)
        yield text[start:end]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--net", action="append", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.output.resolve() == args.base.resolve():
        raise RuntimeError("output must differ from base")
    if args.output.exists() and not args.force:
        raise RuntimeError(f"output exists: {args.output}")

    base = args.base.read_text(encoding="utf-8")
    source = args.source.read_text(encoding="utf-8")
    selected_nets = set(args.net)
    for net_name in selected_nets:
        if f'(net "{net_name}")' not in base:
            raise RuntimeError(f"net absent from base: {net_name}")

    existing_uuids = set(re.findall(r'\(uuid\s+"?([0-9a-f-]{36})"?\)', base))
    additions: list[str] = []
    for block in copper_blocks(source):
        net_match = re.search(r'\(net\s+"([^"]+)"\)', block)
        uuid_match = re.search(r'\(uuid\s+"?([0-9a-f-]{36})"?\)', block)
        if (
            net_match is None
            or uuid_match is None
            or net_match.group(1) not in selected_nets
            or uuid_match.group(1) in existing_uuids
        ):
            continue
        additions.append("\t" + block)
        existing_uuids.add(uuid_match.group(1))

    insertion = base.find("\n\t(zone")
    if insertion < 0:
        insertion = base.rfind("\n)")
    if insertion < 0:
        raise RuntimeError("could not locate PCB insertion point")
    result = base[:insertion] + "\n" + "\n".join(additions) + base[insertion:]
    args.output.write_text(result, encoding="utf-8", newline="\n")
    print(f"MERGED blocks={len(additions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
