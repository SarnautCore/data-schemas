"""Cross-field checks for placement documents and their map locators."""

from __future__ import annotations

from _common import Document


def placement_invariant_errors(document: Document) -> list[str]:
    data = document.data
    if not isinstance(data, dict) or data.get("kind") != "placements":
        return []

    errors: list[str] = []
    map_slug = data.get("map")
    map_resource = data.get("map_resource")
    if isinstance(map_slug, str) and isinstance(map_resource, str) and map_slug != map_resource:
        errors.append(
            f"/map_resource: {map_resource!r} differs from document map {map_slug!r}"
        )

    seen: set[str] = set()
    for index, locator in enumerate(data.get("locators") or []):
        if not isinstance(locator, dict):
            continue
        script_id = locator.get("script_id")
        if not isinstance(script_id, str):
            continue
        if any(character in "/\\" or ord(character) < 32 or ord(character) == 127 for character in script_id):
            errors.append(
                f"/locators/{index}/script_id: {script_id!r} contains a row-key separator "
                "or control character"
            )
        if script_id in seen:
            errors.append(
                f"/locators/{index}/script_id: {script_id!r} appears twice in map "
                f"{map_resource!r}"
            )
        seen.add(script_id)
    return errors
