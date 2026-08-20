#!/usr/bin/env python3
"""Run the negative fixtures: every one of them must be rejected.

A schema that accepts everything passes the positive tests too, so these are
the fixtures that make additionalProperties and the canonical-id patterns load
bearing. Every document schema must carry at least an unknown-property fixture
and a malformed-id fixture; the check for that is here rather than in a
README, because a README does not fail the build.
"""

from __future__ import annotations

import sys

from _common import (
    SHARED_SCHEMAS,
    load_schemas,
    negative_fixtures,
    validators,
)

REQUIRED_FIXTURES = ("unknown-property", "malformed-id")


def main() -> int:
    compiled = validators()
    failures: list[str] = []
    seen: dict[str, set[str]] = {}
    count = 0

    for stem, fixture in negative_fixtures():
        count += 1
        if stem not in compiled:
            failures.append(f"{fixture.rel}: no schema named {stem}.schema.json")
            continue
        seen.setdefault(stem, set()).add(fixture.path.stem)
        errors = list(compiled[stem].iter_errors(fixture.data))
        if errors:
            print(f"ok   {fixture.rel}  rejected by {stem}.schema.json: {errors[0].message[:96]}")
        else:
            failures.append(
                f"{fixture.rel}: accepted by {stem}.schema.json but the fixture exists to be rejected"
            )

    for stem in sorted(set(load_schemas()) - SHARED_SCHEMAS):
        present = seen.get(stem, set())
        for required in REQUIRED_FIXTURES:
            if required not in present:
                failures.append(f"{stem}.schema.json: missing negative fixture demo/negative/{stem}/{required}.yaml")

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)
    if failures:
        return 1
    print(f"\n{count} negative fixtures rejected as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
