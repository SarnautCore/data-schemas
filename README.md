# data-schemas

JSON Schemas for SarnautCore game-design YAML + a small hand-authored demo dataset (no MY.GAMES content).

## About SarnautCore

This repository is part of SarnautCore, a fan-driven, non-commercial, open-source recreation kit for Allods Online.

The project charter and the architecture decision records live in [SarnautCore/docs](https://github.com/SarnautCore/docs). Read those before opening a pull request here.

## Clean-room posture

SarnautCore is built clean-room. This project never distributes game assets or data owned by MY.GAMES. Everything in this repository is written from scratch: the schemas describe the shape of design data, and the demo dataset is invented content used for tests and examples. Do not commit extracted or derived game data here.

`scripts/check_no_private_data.py` enforces that in CI: it rejects unexpected file
types, non-UTF-8 content, Cyrillic text, and any demo `path` or `href` that does
not point into `Demo/`.

## Layout

- `schemas/`: JSON Schema documents that validate the game-design YAML.
- `demo/`: a hand-authored dataset that validates against those schemas and forms a closed reference graph.
- `demo/negative/`: fixtures that must be **rejected**, one directory per schema.
- `scripts/`: the checks CI runs.

## Schema inventory

Every schema is draft 2020-12 and is identified by `https://schemas.sarnautcore.org/<file>`.
That is an identifier namespace, not a website: nothing fetches it.

| Schema | Documents | Zone-scoped |
|---|---|---|
| `common.schema.json` | none — shared `$defs` only | n/a |
| `item.schema.json` | `item.*` | no |
| `quest.schema.json` | `quest.*` | **yes** |
| `route.schema.json` | `route.*` | **yes** |
| `spawn.schema.json` | `spawn.*` (tables, placements), `mob.*` | **yes** |
| `zone.schema.json` | `zone.*` | is the zone |
| `mobkind.schema.json` | `mobkind.*`, `mobclass.*`, `mobquality.*` | no |
| `loot-table.schema.json` | `loot.*` | no |
| `faction.schema.json` | `faction.*` | no |
| `locale.schema.json` | `locale.*` | no |
| `chargen.schema.json` | `chargen.*` | no |
| `ability.schema.json` | `ability.*` | no |

`ability.schema.json` is deliberately minimal. It exists because
[ADR 0032](https://github.com/SarnautCore/docs/blob/main/adr/0032-character-creation.md)
puts `starting_abilities` on the chargen document and requires those ids to resolve.
Full ability and spell extraction is queued per ADR 0003.

## The zone-free base

`common.schema.json` holds the vocabulary every document type shares: `slug`,
`canonicalId`, `zoneId`, `locKey`, `resourceRef`, `source`, `base`, `position`,
`orientation` and `statEntry`.

`$defs.base` carries `schema_version`, `id`, `source_type` and `_source`, and
**no `zone`**. Mob kinds, loot tables, factions, locales, chargen options and
abilities are global resources under `/Mechanics` and `/World/LootTables` with no
zone at all, so requiring one there would have meant either lying in the data or
adding zone-less variants to an already-discriminated `oneOf`. Schemas whose
documents genuinely belong to one zone — `spawn`, `quest`, `route` — add and
require `zone` themselves. `demo/negative/*/missing-zone.yaml` proves they still
require it; `demo/negative/mobkind/zone-on-global.yaml` proves a global document
cannot smuggle one in.

## Consuming these schemas

Schemas reference each other by **relative URI** (`common.schema.json#/$defs/base`),
resolved against the referring schema's `$id`. A validator must therefore be given
every file in `schemas/` up front, because nothing may be fetched at validation
time. In Python that is a `referencing.Registry` built from the directory
(`scripts/_common.py`); in Rust, `jsonschema::options().with_retriever(...)` with a
retriever that maps the `https://schemas.sarnautcore.org/` prefix onto the local
schema directory and refuses everything else.

The extractor validates generated YAML before writing when invoked with
`--validate`. Pass `--schema-dir` explicitly or keep this repository beside the
`tools` and private `data` repositories so the CLI can find `schemas/`.

## The demo reference graph

`scripts/check_references.py` reports dangling references and must report zero.
What counts as an edge:

- A `{id, href}` resource ref **that carries an `id`**. `href` alone means the
  extractor has not mapped that source path to a canonical id yet; those are
  counted and printed, never failed, because an unmapped ref is honest about
  coverage while a wrong id is not.
- A canonical id written inline in `zone`, `zone_id`, `route`, `item_id` or
  `faction`, and every entry of `prototype_chain`, `starting_abilities` and
  `starting_quests`.
- Every string under a `loc_ref`, which must be supplied by a locale document.

`race` and `class` on a chargen document are canonical ids but are **not** edges:
M2 has no race or class document type, and inventing two empty schemas to give
them somewhere to point would be worse than saying so.

The same script enforces the cross-field constraints JSON Schema cannot express —
the loot tree's parallel `chances` array, `max_number >= min_number`, route links
naming real points, zone bounds and level ranges being the right way round, and map
slugs naming a map the zone declares.

## Running the checks

```sh
python -m pip install -r scripts/requirements.txt
python scripts/validate_schemas.py      # schemas vs. the draft 2020-12 meta-schema
python scripts/validate_demo.py         # demo documents vs. their schema
python scripts/check_references.py      # dangling references and cross-field invariants
python scripts/check_negative.py        # fixtures that must be rejected
python scripts/check_no_private_data.py # clean-room guard
```

A demo document is routed to its schema by the first segment of its `id`, via
`SCHEMA_BY_ID_PREFIX` in `scripts/_common.py`. `validate_demo.py` fails if any
document schema has no demo document, and `check_negative.py` fails if any is
missing its `unknown-property` or `malformed-id` fixture — an uncovered schema is
one that has never been shown to accept or reject anything.

## License

AGPL-3.0. See [LICENSE](LICENSE).
