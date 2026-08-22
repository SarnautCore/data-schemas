#!/usr/bin/env python3
"""Report dangling references across the demo dataset, plus the cross-field
invariants JSON Schema cannot express.

What counts as a reference
--------------------------
* A resource ref that carries an ``id``. ``href`` alone means the
  extractor has not mapped that source path to a canonical id yet; those are
  counted and printed, not failed, because an unmapped ref is honest about
  coverage while a wrong id is a lie.
* A string in one of ``REF_STRING_FIELDS`` — ``zone``, ``route``, ``item_id``
  and friends — which is a canonical id written inline rather than as a ref
  object.
* Every string under a ``loc_ref``, which is a localization key and must be
  supplied by some locale document.

What deliberately does not count: ``race`` and ``class`` on a chargen document.
They are canonical ids, but M2 has no race or class document type (ADR 0032
ships one option and defers the rest), so there is nothing for them to resolve
against and pretending otherwise would just mean inventing two empty schemas.

Cross-field invariants
----------------------
JSON Schema cannot compare two arrays' lengths or two sibling numbers, so the
constraints that live in prose in the specs are enforced here: the loot tree's
parallel ``chances`` array (loot.md section 4), ``max_number >= min_number``,
route links pointing at real points, zone bounds and level ranges being the
right way round, and map slugs naming a map the zone declares.
"""

from __future__ import annotations

import sys
from typing import Any, Iterator

from _common import Document, demo_documents
from _placement_contract import placement_invariant_errors

# Fields whose string value is a canonical id pointing at another document.
REF_STRING_FIELDS = frozenset({"faction", "item_id", "quest", "route", "zone", "zone_id"})

# Fields whose value is a list of canonical ids.
REF_LIST_FIELDS = frozenset({"prototype_chain", "starting_abilities", "starting_quests"})


def _is_resource_ref(node: Any) -> bool:
    if not isinstance(node, dict) or not set(node) <= {"id", "row_type", "href"}:
        return False
    return "href" in node or "row_type" in node or set(node) == {"id"}


def _iter_loc_keys(node: Any, pointer: str) -> Iterator[tuple[str, str]]:
    if isinstance(node, str):
        yield pointer, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_loc_keys(value, f"{pointer}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_loc_keys(value, f"{pointer}/{index}")


def collect(
    node: Any,
    pointer: str,
    doc_refs: list[tuple[str, str]],
    loc_refs: list[tuple[str, str]],
    unmapped: list[str],
) -> None:
    if _is_resource_ref(node):
        if "id" in node:
            doc_refs.append((pointer, node["id"]))
        else:
            unmapped.append(pointer)
        return

    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{pointer}/{key}"
            if key == "loc_ref":
                loc_refs.extend(_iter_loc_keys(value, child))
            elif key in REF_STRING_FIELDS and isinstance(value, str):
                doc_refs.append((child, value))
            elif key in REF_LIST_FIELDS and isinstance(value, list):
                for index, item in enumerate(value):
                    if isinstance(item, str):
                        doc_refs.append((f"{child}/{index}", item))
            else:
                collect(value, child, doc_refs, loc_refs, unmapped)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            collect(value, f"{pointer}/{index}", doc_refs, loc_refs, unmapped)


def check_loot_node(node: Any, pointer: str, problems: list[str], rel: str, depth: int) -> int:
    """Validate one node and return the deepest *container* level beneath it.

    ``depth`` is the container level this node would occupy if it is a
    container. Leaves occupy none, so they report ``depth - 1``: that keeps the
    returned number comparable with loot.md's MAX_TREE_DEPTH, which counts
    container levels only.
    """
    if not isinstance(node, dict):
        return depth - 1
    kind = node.get("node")
    if kind in {"and", "or"}:
        entries = node.get("entries") or []
        chances = node.get("chances") or []
        if len(entries) != len(chances):
            problems.append(
                f"{rel}: {pointer}: {kind} node has {len(entries)} entries but "
                f"{len(chances)} chances; they are positionally paired"
            )
        deepest = depth
        for index, child in enumerate(entries):
            deepest = max(deepest, check_loot_node(child, f"{pointer}/entries/{index}", problems, rel, depth + 1))
        return deepest
    if kind in {"single-item", "money"}:
        low, high = node.get("min_number"), node.get("max_number")
        if isinstance(low, int) and isinstance(high, int) and high < low:
            problems.append(f"{rel}: {pointer}: max_number {high} is below min_number {low}")
    return depth - 1


def counter_binding_invariant_errors(
    document: Document, by_id: dict[str, Document]
) -> list[str]:
    data = document.data
    if not isinstance(data, dict) or not (document.doc_id or "").startswith("script."):
        return []
    quest = by_id.get(data.get("quest"))
    if quest is None or not isinstance(quest.data, dict):
        return []
    objectives = quest.data.get("objectives") or []
    errors: list[str] = []
    for position, binding in enumerate(data.get("counters") or []):
        if not isinstance(binding, dict):
            continue
        index = binding.get("objective")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not 0 <= index < len(objectives)
        ):
            errors.append(
                f"/counters/{position}/objective: {index!r} is outside quest "
                f"{quest.doc_id!r}, which has {len(objectives)} objectives"
            )
            continue
        objective = objectives[index]
        expected = objective.get("objective_id") if isinstance(objective, dict) else None
        objective_id = binding.get("objective_id")
        if isinstance(expected, str) and objective_id != expected:
            errors.append(
                f"/counters/{position}/objective_id {objective_id!r} does not match "
                f"quest objective {index} id {expected!r}"
            )
    return errors


def check_invariants(documents: list[Document], by_id: dict[str, Document]) -> list[str]:
    problems: list[str] = []
    zone_maps: dict[str, set[str]] = {}
    locator_keys: dict[str, Document] = {}

    for document in documents:
        data = document.data
        if not isinstance(data, dict):
            continue
        doc_id = document.doc_id or ""

        if doc_id.startswith("zone."):
            maps = set(data.get("maps") or [])
            zone_maps[doc_id] = maps
            levels = data.get("level_range") or {}
            if levels.get("min", 0) > levels.get("max", 0):
                problems.append(f"{document.rel}: level_range.min is above level_range.max")
            bounds = data.get("bounds") or {}
            low, high = bounds.get("min") or {}, bounds.get("max") or {}
            for axis in ("x", "y", "z"):
                if low.get(axis, 0) > high.get(axis, 0):
                    problems.append(f"{document.rel}: bounds.min.{axis} is above bounds.max.{axis}")
            spawn_map = (data.get("player_spawn") or {}).get("map")
            if spawn_map is not None and spawn_map not in maps:
                problems.append(f"{document.rel}: player_spawn.map {spawn_map!r} is not in maps")

        if doc_id.startswith("loot."):
            depth = check_loot_node(data.get("root"), "/root", problems, document.rel, 1)
            if depth > 8:
                problems.append(f"{document.rel}: container depth {depth} exceeds MAX_TREE_DEPTH of 8")

        if doc_id.startswith("route."):
            indices = [point.get("index") for point in data.get("points") or []]
            if len(indices) != len(set(indices)):
                problems.append(f"{document.rel}: duplicate point indices")
            known = set(indices)
            for position, link in enumerate(data.get("links") or []):
                for end in ("from", "to"):
                    if link.get(end) not in known:
                        problems.append(f"{document.rel}: links/{position}/{end} names point {link.get(end)}, which does not exist")

        if doc_id.startswith("locale."):
            keys = [entry.get("key") for entry in data.get("entries") or []]
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            for key in duplicates:
                problems.append(f"{document.rel}: duplicate locale key {key!r}")

        problems.extend(
            f"{document.rel}: {error}" for error in placement_invariant_errors(document)
        )
        problems.extend(
            f"{document.rel}: {error}"
            for error in counter_binding_invariant_errors(document, by_id)
        )
        if data.get("kind") == "placements" and isinstance(data.get("map_resource"), str):
            for locator in data.get("locators") or []:
                if not isinstance(locator, dict) or not isinstance(locator.get("script_id"), str):
                    continue
                key = f"{data['map_resource']}/{locator['script_id']}"
                if key in locator_keys:
                    problems.append(
                        f"{document.rel}: map locator key {key!r} is already declared by "
                        f"{locator_keys[key].rel}"
                    )
                locator_keys[key] = document

    # Map slugs on zone-scoped documents must name a map the zone declares.
    for document in documents:
        data = document.data
        if not isinstance(data, dict):
            continue
        zone, slug = data.get("zone"), data.get("map")
        if isinstance(zone, str) and isinstance(slug, str) and zone in zone_maps:
            if slug not in zone_maps[zone]:
                problems.append(f"{document.rel}: map {slug!r} is not one of {zone}'s maps")

    return problems


def main() -> int:
    documents = demo_documents()
    if not documents:
        print("no demo documents found", file=sys.stderr)
        return 1

    by_id: dict[str, Document] = {}
    problems: list[str] = []
    for document in documents:
        doc_id = document.doc_id
        if doc_id is None:
            problems.append(f"{document.rel}: no top-level id")
            continue
        if doc_id in by_id:
            problems.append(f"{document.rel}: id {doc_id!r} is already defined by {by_id[doc_id].rel}")
            continue
        by_id[doc_id] = document

    # QuestCountId records are embedded as counter bindings in M3-09's
    # QuestScript rows. They are valid ContentRef targets even though this
    # schema version has no standalone quest-count-id document.
    known_ids = set(by_id)
    for document in documents:
        data = document.data
        if not isinstance(data, dict) or not (document.doc_id or "").startswith("zone."):
            continue
        known_ids.update(item for item in data.get("maps") or [] if isinstance(item, str))
    count_owners: dict[str, Document] = {}
    for document in documents:
        data = document.data
        if not isinstance(data, dict) or not (document.doc_id or "").startswith("script."):
            continue
        for binding in data.get("counters") or []:
            if not isinstance(binding, dict) or not isinstance(binding.get("count_id"), str):
                continue
            count_id = binding["count_id"]
            if count_id in count_owners:
                problems.append(
                    f"{document.rel}: count id {count_id!r} is already declared by "
                    f"{count_owners[count_id].rel}"
                )
            count_owners[count_id] = document
            known_ids.add(count_id)

    locale_keys: set[str] = set()
    for document in documents:
        if (document.doc_id or "").startswith("locale.") and isinstance(document.data, dict):
            for entry in document.data.get("entries") or []:
                if isinstance(entry, dict) and isinstance(entry.get("key"), str):
                    locale_keys.add(entry["key"])

    dangling: list[str] = []
    unmapped_total = 0
    edges = 0

    for document in documents:
        doc_refs: list[tuple[str, str]] = []
        loc_refs: list[tuple[str, str]] = []
        unmapped: list[str] = []
        collect(document.data, "", doc_refs, loc_refs, unmapped)
        unmapped_total += len(unmapped)
        edges += len(doc_refs) + len(loc_refs)

        for pointer, target in doc_refs:
            if target not in known_ids:
                dangling.append(f"{document.rel}: {pointer}: no document has id {target!r}")
        for pointer, key in loc_refs:
            if key not in locale_keys:
                dangling.append(f"{document.rel}: {pointer}: no locale document supplies key {key!r}")

    problems.extend(check_invariants(documents, by_id))

    for line in dangling:
        print(f"DANGLING {line}", file=sys.stderr)
    for line in problems:
        print(f"INVALID  {line}", file=sys.stderr)

    print(f"documents:            {len(documents)}")
    print(f"resolved references:  {edges - len(dangling)}")
    print(f"dangling references:  {len(dangling)}")
    print(f"unmapped href refs:   {unmapped_total} (href with no canonical id; not an error)")
    print(f"invariant violations: {len(problems)}")

    return 1 if dangling or problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
