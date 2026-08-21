#!/usr/bin/env python3
"""Check map locator identity rules on every positive placement demo."""

from __future__ import annotations

import json
import sys

from _common import DEMO_DIR, demo_documents
from _placement_contract import placement_invariant_errors

GOLDEN_PATH = DEMO_DIR / "map-locators.golden.json"


def main() -> int:
    documents = 0
    rows: list[dict[str, object]] = []
    seen_keys: set[str] = set()
    failures: list[str] = []
    for document in demo_documents():
        data = document.data
        if not isinstance(data, dict) or data.get("kind") != "placements":
            continue
        documents += 1
        map_id = data.get("map_resource")
        for locator in data.get("locators") or []:
            if not isinstance(map_id, str) or not isinstance(locator, dict):
                continue
            script_id = locator.get("script_id")
            if not isinstance(script_id, str):
                continue
            row_key = f"{map_id}/{script_id}"
            if row_key in seen_keys:
                failures.append(f"{document.rel}: duplicate map locator row key {row_key!r}")
            seen_keys.add(row_key)
            rows.append(
                {
                    "row_key": row_key,
                    "map_id": map_id,
                    "script_id": script_id,
                    "position": locator.get("position"),
                }
            )
        errors = placement_invariant_errors(document)
        if errors:
            failures.extend(f"{document.rel}: {error}" for error in errors)
        else:
            print(f"ok   {document.rel}")

    if documents == 0:
        failures.append("no placement demo documents found")
    if not rows:
        failures.append("no positive map locator fixture found")
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))["rows"]
    rows.sort(key=lambda row: str(row["row_key"]).encode("utf-8"))
    if rows != expected:
        failures.append(f"map locator rows differ from {GOLDEN_PATH.name}: {rows!r}")
    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"\n{documents} placement documents match {len(rows)} golden map locator row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
