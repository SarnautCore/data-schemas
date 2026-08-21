"""Shared loading helpers for the data-schemas check scripts.

Everything here is offline by construction: the registry is built from the
files in ``schemas/`` and its retriever refuses to fetch anything, so a
``$ref`` at a URI this repository does not ship is a hard error rather than an
HTTP request. ``https://schemas.sarnautcore.org/`` is an identifier namespace,
not a website.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
DEMO_DIR = REPO_ROOT / "demo"
NEGATIVE_DIR = DEMO_DIR / "negative"
# The overlay layer manifest of ADR 0029. Build configuration, not content.
LAYERS_FILE_NAME = "layers.yaml"

META_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
ID_NAMESPACE = "https://schemas.sarnautcore.org/"

# Schemas that define no document type. Nothing validates against them
# directly, so they get no demo document and no negative fixtures.
SHARED_SCHEMAS = frozenset({"common"})

# The first dot-separated segment of a document id decides which schema
# validates it. Several id prefixes share one schema: a spawn document is a
# table, a mob template or a placement list, and the creature taxonomy under
# /Mechanics is three related record types in one file.
SCHEMA_BY_ID_PREFIX: dict[str, str] = {
    "ability": "ability",
    "chargen": "chargen",
    "faction": "faction",
    "item": "item",
    "levelcurve": "level-curve",
    "locale": "locale",
    "loot": "loot-table",
    "mob": "spawn",
    "mobclass": "mobkind",
    "mobkind": "mobkind",
    "mobquality": "mobkind",
    "quest": "quest",
    "route": "route",
    "script": "quest-script",
    "spawn": "spawn",
    "trigger": "script-trigger",
    "zone": "zone",
}


@dataclass(frozen=True)
class Document:
    path: Path
    data: Any

    @property
    def rel(self) -> str:
        return self.path.relative_to(REPO_ROOT).as_posix()

    @property
    def doc_id(self) -> str | None:
        if isinstance(self.data, dict):
            value = self.data.get("id")
            if isinstance(value, str):
                return value
        return None


def schema_paths() -> list[Path]:
    return sorted(SCHEMA_DIR.glob("*.schema.json"))


def schema_stem(path: Path) -> str:
    return path.name[: -len(".schema.json")]


def load_schemas() -> dict[str, Any]:
    """Read every schema file, keyed by its stem (``item``, ``loot-table``, ...)."""
    schemas: dict[str, Any] = {}
    for path in schema_paths():
        with path.open(encoding="utf-8") as handle:
            schemas[schema_stem(path)] = json.load(handle)
    return schemas


def _refuse_retrieval(uri: str) -> Resource:
    raise RuntimeError(
        f"refused to resolve {uri!r}: schema validation must not touch the network, "
        f"and no schema in {SCHEMA_DIR.name}/ declares that $id"
    )


def build_registry(schemas: dict[str, Any]) -> Registry:
    resources = []
    for stem, schema in schemas.items():
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise SystemExit(f"{stem}.schema.json has no string $id")
        resources.append((schema_id, Resource.from_contents(schema, default_specification=DRAFT202012)))
    return Registry(retrieve=_refuse_retrieval).with_resources(resources)


def validators() -> dict[str, Draft202012Validator]:
    schemas = load_schemas()
    registry = build_registry(schemas)
    return {
        stem: Draft202012Validator(schema, registry=registry)
        for stem, schema in schemas.items()
    }


def load_yaml(path: Path) -> Document:
    with path.open(encoding="utf-8") as handle:
        return Document(path=path, data=yaml.safe_load(handle))


def demo_documents() -> list[Document]:
    """Every demo document that is expected to validate.

    The search is recursive so that overlay datasets under ``demo/overlays/``
    are held to the same schemas and the same reference graph as the base
    documents they layer over. An overlay that only the pack compiler ever
    reads is an unvalidated corner of the fixture set.

    The negative fixtures live under ``demo/negative/`` and are excluded here;
    they are exercised by ``check_negative.py``.

    ``demo/overlays/layers.yaml`` is excluded too. It is the layer manifest
    ADR 0029 gives the pack compiler, not a content document: it has no id and
    no schema, and it is the one YAML file under ``demo/`` that is build
    configuration rather than content.
    """
    paths = sorted(
        path
        for path in DEMO_DIR.rglob("*.yaml")
        if NEGATIVE_DIR not in path.parents and path.name != LAYERS_FILE_NAME
    )
    return [load_yaml(path) for path in paths]


def negative_fixtures() -> Iterator[tuple[str, Document]]:
    """Yield ``(schema stem, fixture)`` for every committed negative fixture."""
    if not NEGATIVE_DIR.is_dir():
        return
    for directory in sorted(p for p in NEGATIVE_DIR.iterdir() if p.is_dir()):
        for path in sorted(directory.glob("*.yaml")):
            yield directory.name, load_yaml(path)


def schema_stem_for(document: Document) -> str:
    doc_id = document.doc_id
    if doc_id is None:
        raise SystemExit(f"{document.rel}: document has no string top-level id")
    prefix = doc_id.split(".", 1)[0]
    stem = SCHEMA_BY_ID_PREFIX.get(prefix)
    if stem is None:
        raise SystemExit(
            f"{document.rel}: id {doc_id!r} has prefix {prefix!r}, "
            f"which is not mapped to a schema in SCHEMA_BY_ID_PREFIX"
        )
    return stem
