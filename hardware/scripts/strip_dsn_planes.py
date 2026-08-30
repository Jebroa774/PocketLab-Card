#!/usr/bin/env python3
"""Remove conductive plane expressions from a Specctra DSN routing copy."""

from __future__ import annotations

import argparse
from pathlib import Path


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
    raise ValueError(f"Unterminated expression at byte {start}")


def strip_planes(text: str) -> tuple[str, int]:
    output: list[str] = []
    cursor = 0
    removed = 0
    while True:
        start = text.find("(plane", cursor)
        if start < 0:
            output.append(text[cursor:])
            break
        after = start + len("(plane")
        if after < len(text) and not text[after].isspace():
            output.append(text[cursor:after])
            cursor = after
            continue
        end = expression_end(text, start)
        output.append(text[cursor:start])
        cursor = end
        removed += 1
    return "".join(output), removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    source = args.input.read_text(encoding="utf-8")
    result, removed = strip_planes(source)
    args.output.write_text(result, encoding="utf-8", newline="\n")
    print(f"Saved {args.output}; removed_planes={removed}")


if __name__ == "__main__":
    main()
