#!/usr/bin/env python3
"""Compile content.proto and compare its script field map with the checked lock.

The descriptor compilation catches protobuf syntax and type errors. The
human-readable lock catches a field rename, number reuse, cardinality change,
or oneof move without relying on generated code from either consumer.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from _common import REPO_ROOT

PROTO_ROOT = REPO_ROOT / "proto"
PROTO_PATH = PROTO_ROOT / "sarnaut" / "content" / "v1" / "content.proto"
LOCK_PATH = PROTO_PATH.with_name("content.script-contract.lock.json")


def _without_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def _block(text: str, kind: str, name: str) -> tuple[str, int]:
    match = re.search(rf"\b{re.escape(kind)}\s+{re.escape(name)}\s*\{{", text)
    if match is None:
        raise ValueError(f"{kind} {name} is absent")
    start = match.end()
    depth = 1
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index], start
    raise ValueError(f"{kind} {name} has no closing brace")


def _enum(text: str, name: str) -> dict[str, int]:
    body, _ = _block(text, "enum", name)
    return {
        field: int(number)
        for field, number in re.findall(r"\b([A-Z][A-Z0-9_]*)\s*=\s*(\d+)\s*;", body)
    }


def _oneof_ranges(body: str) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\boneof\s+(\w+)\s*\{", body):
        depth = 1
        start = match.end()
        for index in range(start, len(body)):
            if body[index] == "{":
                depth += 1
            elif body[index] == "}":
                depth -= 1
                if depth == 0:
                    ranges.append((start, index, match.group(1)))
                    break
    return ranges


def _message(text: str, name: str) -> dict[str, dict[str, Any]]:
    body, _ = _block(text, "message", name)
    oneofs = _oneof_ranges(body)
    fields: dict[str, dict[str, Any]] = {}
    pattern = re.compile(
        r"(?m)^\s*(?:(repeated|optional)\s+)?([A-Za-z_][.A-Za-z0-9_]*)\s+"
        r"([a-z_][a-z0-9_]*)\s*=\s*(\d+)\s*;"
    )
    for match in pattern.finditer(body):
        label, field_type, field_name, number = match.groups()
        shape: dict[str, Any] = {
            "type": field_type,
            "number": int(number),
            "label": label or "singular",
        }
        for start, end, oneof_name in oneofs:
            if start <= match.start() < end:
                shape["oneof"] = oneof_name
                break
        fields[field_name] = shape
    return fields


def _compile() -> str | None:
    protoc = shutil.which("protoc")
    if protoc is None:
        return "protoc is not installed; content.proto was not descriptor-compiled"
    with tempfile.TemporaryDirectory(prefix="sarnaut-proto-") as temporary:
        descriptor = Path(temporary) / "content.pb"
        result = subprocess.run(
            [
                protoc,
                "--proto_path=.",
                f"--descriptor_set_out={descriptor}",
                PROTO_PATH.relative_to(PROTO_ROOT).as_posix(),
            ],
            cwd=PROTO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return result.stderr.strip() or f"protoc exited {result.returncode}"
        if not descriptor.is_file() or descriptor.stat().st_size == 0:
            return "protoc wrote no descriptor bytes"
    return None


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    text = _without_comments(PROTO_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    compile_error = _compile()
    if compile_error:
        failures.append(f"descriptor compile: {compile_error}")
    else:
        print("ok   content.proto descriptor compile")

    for name, expected in lock["enums"].items():
        actual = _enum(text, name)
        if actual != expected:
            failures.append(f"enum {name}: got {actual!r}, lock requires {expected!r}")
        else:
            print(f"ok   enum {name}")

    for name, expected in lock["messages"].items():
        actual = _message(text, name)
        if actual != expected:
            failures.append(f"message {name}: got {actual!r}, lock requires {expected!r}")
        else:
            print(f"ok   message {name}")

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        return 1
    print(
        f"\n{len(lock['enums'])} enums and {len(lock['messages'])} messages match the proto lock"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
