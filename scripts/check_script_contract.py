#!/usr/bin/env python3
"""Check ADR 0036's row-level script invariants on every positive demo."""

from __future__ import annotations

import sys

from _common import demo_documents
from _script_contract import script_invariant_errors


def main() -> int:
    rows = 0
    failures: list[str] = []
    for document in demo_documents():
        doc_id = document.doc_id or ""
        if not doc_id.startswith(("script.", "trigger.")):
            continue
        rows += 1
        errors = script_invariant_errors(document)
        if errors:
            failures.extend(f"{document.rel}: {error}" for error in errors)
        else:
            print(f"ok   {document.rel}")

    if rows == 0:
        failures.append("no quest-script or shared-trigger demo rows found")
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"\n{rows} script rows satisfy ADR 0036 invariants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
