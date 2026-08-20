#!/usr/bin/env python3
"""Fail if anything in this repository looks like extracted game data.

The clean-room posture (ADR 0011) says this public repository holds schemas
and invented demo content and nothing else. That is easy to state and easy to
break by accident — someone debugging an extractor pastes a real document into
demo/ to reproduce a failure and forgets to delete it. So it is checked:

1. Every file is one of a small set of expected types. An .xdb, a .dds or a
   .locpack has no reason to exist here.
2. Every source path and every href in the demo set points into ``Demo/``.
   Real extracted documents carry real reference-tree paths, and the prefix is
   the cheapest thing that distinguishes them.
3. No file contains Cyrillic text. The original data is Russian-first, so a
   Cyrillic string is a display string that came from somewhere it should not
   have.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterator

from _common import DEMO_DIR, REPO_ROOT, load_yaml

ALLOWED_SUFFIXES = frozenset({".json", ".md", ".py", ".txt", ".yaml", ".yml", ""})
SKIPPED_DIRECTORIES = frozenset({".git", "__pycache__", ".venv"})
DEMO_PATH_PREFIXES = ("Demo/", "/Demo/")


def tracked_files() -> Iterator[Path]:
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIPPED_DIRECTORIES for part in path.relative_to(REPO_ROOT).parts):
            continue
        yield path


def iter_strings(node: Any, pointer: str = "") -> Iterator[tuple[str, str, str]]:
    """Yield ``(pointer, key, value)`` for every string leaf in a document."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{pointer}/{key}"
            if isinstance(value, str):
                yield child, key, value
            else:
                yield from iter_strings(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child = f"{pointer}/{index}"
            if isinstance(value, str):
                yield child, "", value
            else:
                yield from iter_strings(value, child)


def has_cyrillic(text: str) -> bool:
    return any("CYRILLIC" in unicodedata.name(char, "") for char in text if ord(char) > 127)


def main() -> int:
    failures: list[str] = []
    checked = 0

    for path in tracked_files():
        checked += 1
        rel = path.relative_to(REPO_ROOT).as_posix()

        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            failures.append(f"{rel}: file type {path.suffix!r} is not expected in this repository")
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(f"{rel}: not UTF-8 text; this repository holds no binary content")
            continue

        if has_cyrillic(text):
            failures.append(f"{rel}: contains Cyrillic text, which no invented demo document should")

    for path in sorted(DEMO_DIR.rglob("*.yaml")):
        document = load_yaml(path)
        for pointer, key, value in iter_strings(document.data):
            if key not in {"href", "path"}:
                continue
            if not value.startswith(DEMO_PATH_PREFIXES):
                failures.append(
                    f"{document.rel}: {pointer}: {key} {value!r} does not point into Demo/; "
                    f"demo documents are invented and their provenance must say so"
                )

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"{checked} files checked; no extracted game data found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
