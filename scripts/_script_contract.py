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


def _field_map(node: dict[str, Any]) -> dict[str, Any]:
    fields = node.get("fields") or []
    if not isinstance(fields, list):
        return {}
    return {
        field.get("name"): field.get("value")
        for field in fields
        if isinstance(field, dict) and isinstance(field.get("name"), str)
    }


def _value_is(value: Any, member: str) -> bool:
    return isinstance(value, dict) and set(value) == {member}


def _audited_opcode_errors(node: dict[str, Any], pointer: str) -> list[str]:
    """Validate canonical fields for opcodes promoted by the M3 audit."""
    opcode = node.get("opcode")
    fields = _field_map(node)
    names = list(fields)
    errors: list[str] = []

    def want(expected: list[str]) -> None:
        if names != expected:
            errors.append(f"{pointer}/fields: {opcode} fields {names!r}, expected {expected!r}")

    if opcode == "DestinationLocator":
        want(["locator", "yaw"])
        locator_value = fields.get("locator")
        locator = locator_value.get("node") if _value_is(locator_value, "node") else None
        if not isinstance(locator, dict):
            errors.append(f"{pointer}/fields/locator: expected MapPointer node")
        else:
            locator_fields = _field_map(locator)
            if (
                locator.get("family") != "basic"
                or locator.get("opcode") != "Struct"
                or list(locator_fields) != ["map", "scriptID"]
            ):
                errors.append(f"{pointer}/fields/locator: expected MapPointer<Locator>")
            map_value = locator_fields.get("map")
            map_ref = map_value.get("reference") if _value_is(map_value, "reference") else None
            if not isinstance(map_ref, dict) or map_ref.get("row_type") != "map":
                errors.append(f"{pointer}/fields/locator/map: expected map reference")
            script_id = locator_fields.get("scriptID")
            if not _value_is(script_id, "text") or not script_id.get("text"):
                errors.append(f"{pointer}/fields/locator/scriptID: expected nonempty text")
        if not _value_is(fields.get("yaw"), "integer"):
            errors.append(f"{pointer}/fields/yaw: expected integer")
    elif opcode == "Guard":
        want(["noticeTarget", "scanRadius"])
        if not _value_is(fields.get("noticeTarget"), "boolean"):
            errors.append(f"{pointer}/fields/noticeTarget: expected boolean")
        if not _value_is(fields.get("scanRadius"), "decimal"):
            errors.append(f"{pointer}/fields/scanRadius: expected exact decimal")
    elif opcode == "PredicateIsAvatar":
        want([])
    elif opcode == "ScalerAllInputDamage":
        want(["attackerConditions", "onlyFromCaster", "scaler", "stackCount"])
        if not _value_is(fields.get("attackerConditions"), "list"):
            errors.append(f"{pointer}/fields/attackerConditions: expected list")
        if not _value_is(fields.get("onlyFromCaster"), "boolean"):
            errors.append(f"{pointer}/fields/onlyFromCaster: expected boolean")
        errors.extend(_scaler_errors(fields.get("scaler"), f"{pointer}/fields/scaler"))
        stack_count = fields.get("stackCount")
        if not _value_is(stack_count, "integer") or stack_count.get("integer", 0) < 1:
            errors.append(f"{pointer}/fields/stackCount: expected positive integer")
    elif opcode == "ScalerAllOutputDamage":
        if names not in (["scaler", "stackCount"], ["group", "scaler", "stackCount"]):
            errors.append(
                f"{pointer}/fields: {opcode} fields {names!r}, expected optional group then scaler and stackCount"
            )
        group = fields.get("group")
        if group is not None and not (
            _value_is(group, "reference") or _value_is(group, "text")
        ):
            errors.append(f"{pointer}/fields/group: expected reference or group id")
        errors.extend(_scaler_errors(fields.get("scaler"), f"{pointer}/fields/scaler"))
        stack_count = fields.get("stackCount")
        if not _value_is(stack_count, "integer") or stack_count.get("integer", 0) < 1:
            errors.append(f"{pointer}/fields/stackCount: expected positive integer")
    return errors


def _scaler_errors(value: Any, pointer: str) -> list[str]:
    scaler = value.get("node") if _value_is(value, "node") else None
    if not isinstance(scaler, dict) or scaler.get("family") != "scaler":
        return [f"{pointer}: expected scaler node"]
    return []


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
        errors.extend(_audited_opcode_errors(node, pointer))
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
