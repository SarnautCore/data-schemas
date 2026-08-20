#!/usr/bin/env python3
"""Validate every demo document against the schema its id prefix selects.

Fails if a document validates against nothing, if it fails its schema, or if
a document schema has no demo coverage at all — an uncovered schema is one
that has never been shown to accept anything.
"""

from __future__ import annotations

import sys

from _common import (
    SHARED_SCHEMAS,
    demo_documents,
    load_schemas,
    schema_stem_for,
    validators,
)


def main() -> int:
    documents = demo_documents()
    if not documents:
        print("no demo documents found", file=sys.stderr)
        return 1

    compiled = validators()
    failures: list[str] = []
    covered: set[str] = set()

    for document in documents:
        stem = schema_stem_for(document)
        covered.add(stem)
        errors = sorted(
            compiled[stem].iter_errors(document.data),
            key=lambda error: list(error.path),
        )
        if errors:
            for error in errors[:10]:
                location = "/".join(str(part) for part in error.path) or "<root>"
                failures.append(f"{document.rel}: {stem}.schema.json: {location}: {error.message}")
        else:
            print(f"ok   {document.rel}  ->  {stem}.schema.json")

    uncovered = sorted(set(load_schemas()) - SHARED_SCHEMAS - covered)
    for stem in uncovered:
        failures.append(f"{stem}.schema.json: no demo document validates against it")

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"\n{len(documents)} demo documents validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
