"""Cross-item checks for ADR 0036 script rows.

JSON Schema checks each field and union value in isolation. It cannot compare
adjacent field names or collect node keys across a recursive row, so those
rules live here and in the pack compiler.
"""

from __future__ import annotations

from typing import Any

from _common import Document

MAX_SCRIPT_NODE_DEPTH = 32
MAX_SCRIPT_ROW_NODES = 4096


def _roots(data: dict[str, Any]) -> list[tuple[str, Any]]:
    doc_id = data.get("id", "")
    if isinstance(doc_id, str) and doc_id.startswith("script."):
        roots: list[tuple[str, Any]] = []
        for field in ("start_impacts", "trigger_agents"):
            values = data.get(field)
            if isinstance(values, list):
                roots.extend((f"/{field}/{index}", node) for index, node in enumerate(values))
        return roots
    if isinstance(doc_id, str) and doc_id.startswith("trigger.") and "root" in data:
        return [("/root", data["root"])]
    return []


def script_invariant_errors(document: Document) -> list[str]:
    """Return row-level script errors with JSON-pointer locations."""
    data = document.data
    if not isinstance(data, dict):
        return []
    doc_id = data.get("id")
    if not isinstance(doc_id, str) or not doc_id.startswith(("script.", "trigger.")):
        return []

    errors: list[str] = []
    node_keys: set[str] = set()
    node_count = 0

    if doc_id.startswith("script."):
        seen_counts: set[str] = set()
        quest_id = data.get("quest")
        for index, binding in enumerate(data.get("counters") or []):
            if not isinstance(binding, dict):
                continue
            count_id = binding.get("count_id")
            if isinstance(count_id, str):
                if count_id in seen_counts:
                    errors.append(f"/counters/{index}/count_id: {count_id!r} is bound twice")
                seen_counts.add(count_id)
            objective_id = binding.get("objective_id")
            if (
                isinstance(quest_id, str)
                and isinstance(objective_id, str)
                and not objective_id.startswith(f"{quest_id}.objective.")
            ):
                errors.append(
                    f"/counters/{index}/objective_id: {objective_id!r} is outside "
                    f"owning quest {quest_id!r}"
                )

    def walk_value(value: Any, pointer: str, depth: int) -> None:
        if not isinstance(value, dict):
            return
        if len(value) != 1:
            errors.append(f"{pointer}: sets {len(value)} ScriptValue members, expected one")
            return
        kind, member = next(iter(value.items()))
        if kind == "node":
            walk_node(member, f"{pointer}/node", depth + 1)
        elif kind == "list" and isinstance(member, list):
            for index, item in enumerate(member):
                walk_value(item, f"{pointer}/list/{index}", depth)

    def walk_node(node: Any, pointer: str, depth: int) -> None:
        nonlocal node_count
        if not isinstance(node, dict):
            return
        node_count += 1
        if depth > MAX_SCRIPT_NODE_DEPTH:
            errors.append(
                f"{pointer}: depth {depth} exceeds MAX_SCRIPT_NODE_DEPTH {MAX_SCRIPT_NODE_DEPTH}"
            )

        key = node.get("key")
        if isinstance(key, str):
            if key != doc_id and not key.startswith(f"{doc_id}/"):
                errors.append(f"{pointer}/key: {key!r} is outside owning row {doc_id!r}")
            if key in node_keys:
                errors.append(f"{pointer}/key: node key {key!r} appears twice")
            node_keys.add(key)

        fields = node.get("fields") or []
        if not isinstance(fields, list):
            return
        names = [field.get("name") for field in fields if isinstance(field, dict)]
        if all(isinstance(name, str) for name in names):
            expected = sorted(names, key=lambda name: name.encode("utf-8"))
            if names != expected or len(names) != len(set(names)):
                errors.append(
                    f"{pointer}/fields: names must be unique and bytewise-sorted; "
                    f"got {names!r}, expected {expected!r}"
                )
        for index, field in enumerate(fields):
            if isinstance(field, dict) and "value" in field:
                walk_value(field["value"], f"{pointer}/fields/{index}/value", depth)

    for pointer, root in _roots(data):
        walk_node(root, pointer, 1)

    if node_count > MAX_SCRIPT_ROW_NODES:
        errors.append(
            f"<row>: {node_count} nodes exceeds MAX_SCRIPT_ROW_NODES {MAX_SCRIPT_ROW_NODES}"
        )
    return errors
