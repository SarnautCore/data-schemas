#!/usr/bin/env python3
"""Check every schema in schemas/ against the draft 2020-12 meta-schema.

Also checks the house rules the meta-schema cannot: that each file declares
2020-12, that its $id is in the project namespace and matches its filename,
and that every schema compiles with only the local registry — which is what
proves no $ref reaches for the network.
"""

from __future__ import annotations

import sys
from typing import Any, Iterator

from jsonschema import Draft202012Validator
from referencing import Resource
from referencing.jsonschema import DRAFT202012

from _common import (
    ID_NAMESPACE,
    META_SCHEMA_URI,
    build_registry,
    load_schemas,
    schema_paths,
    schema_stem,
)


def _iter_refs(node: Any, pointer: str = "") -> Iterator[tuple[str, str]]:
    """Yield ``(json pointer, $ref value)`` for every $ref in a schema."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{pointer}/{key}"
            if key == "$ref" and isinstance(value, str):
                yield pointer or "/", value
            else:
                yield from _iter_refs(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_refs(value, f"{pointer}/{index}")


def main() -> int:
    paths = schema_paths()
    if not paths:
        print("no schemas found", file=sys.stderr)
        return 1

    schemas = load_schemas()
    registry = build_registry(schemas)
    failures: list[str] = []

    for path in paths:
        stem = schema_stem(path)
        schema = schemas[stem]

        declared = schema.get("$schema")
        if declared != META_SCHEMA_URI:
            failures.append(f"{path.name}: $schema is {declared!r}, expected {META_SCHEMA_URI!r}")

        expected_id = f"{ID_NAMESPACE}{path.name}"
        if schema.get("$id") != expected_id:
            failures.append(f"{path.name}: $id is {schema.get('$id')!r}, expected {expected_id!r}")

        try:
            Draft202012Validator.check_schema(schema)
        except Exception as error:  # noqa: BLE001 - reported, not handled
            failures.append(f"{path.name}: not a valid draft 2020-12 schema: {error}")
            continue

        # Resolve every $ref eagerly. Lazy resolution would only surface a typo
        # in a cross-file pointer if some demo document happened to reach that
        # branch, which makes an unused broken $ref invisible until the day it
        # is used.
        resolver = registry.resolver_with_root(
            Resource.from_contents(schema, default_specification=DRAFT202012)
        )
        for pointer, ref in _iter_refs(schema):
            try:
                resolver.lookup(ref)
            except Exception as error:  # noqa: BLE001 - reported, not handled
                failures.append(f"{path.name}: {pointer}: cannot resolve $ref {ref!r}: {error}")

        print(f"ok   {path.name}")

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"\n{len(paths)} schemas are valid draft 2020-12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
