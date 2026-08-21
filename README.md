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
- `demo/`: a hand-authored dataset that validates against those schemas and forms
  a closed reference graph. It is also the source of the golden runtime pack that
  `server` and `client` tests share, so treat a change here as a change to those
  tests.
- `demo/negative/`: fixtures that must be **rejected**, one directory per schema.
- `demo/overlays/`: extra documents that layer over the base demo set with
  `sarnaut-pack build --overlay`. They validate against the same schemas and
  join the same reference graph, because an overlay only the pack compiler ever
  reads is an unvalidated corner of the fixture set.
- `proto/`: the `sarnaut.content.v1` row messages of the compiled runtime pack
  ([ADR 0029](https://github.com/SarnautCore/docs/blob/main/adr/0029-runtime-pack-format.md)).
  JSON Schema stays authoritative for the authored YAML; these describe the
  compiled row shape. The pack writer in `tools` and the reader in `server` each
  vendor a copy of this directory for a hermetic build, and those copies must
  stay identical to it. `content.script-contract.lock.json` records the field
  names, numbers, cardinalities and oneof membership of the script and locator
  rows added during M3, plus the stable quest-objective contract they consume.
- `scripts/`: the checks CI runs.

## Schema inventory

Every schema is draft 2020-12 and is identified by `https://schemas.sarnautcore.org/<file>`.
That is an identifier namespace, not a website: nothing fetches it.

| Schema | Documents | Zone-scoped |
|---|---|---|
| `common.schema.json` | none — shared `$defs` only | n/a |
| `item.schema.json` | `item.*` | no |
| `quest.schema.json` | `quest.*` | **yes** |
| `quest-script.schema.json` | `script.*` | **yes** |
| `script-trigger.schema.json` | `trigger.*` | **yes** |
| `route.schema.json` | `route.*` | **yes** |
| `spawn.schema.json` | `spawn.*` (tables, placements), `mob.*` | **yes** |
| `zone.schema.json` | `zone.*` | is the zone |
| `mobkind.schema.json` | `mobkind.*`, `mobclass.*`, `mobquality.*` | no |
| `loot-table.schema.json` | `loot.*` | no |
| `faction.schema.json` | `faction.*` | no |
| `locale.schema.json` | `locale.*` | no |
| `chargen.schema.json` | `chargen.*` | no |
| `ability.schema.json` | `ability.*` | no |
| `level-curve.schema.json` | `levelcurve.*` | no |

`level-curve.schema.json` is the one schema here whose documents are authored
rather than extracted, and it is written the other way round to match:
`curation_note` is required and `_source` is optional. `mechanics/combat.md`
section 7.1 searched the reference tree for the per-level base HP/DPS the
`MobKind` multipliers scale and established that it is not there, which makes
the curve a curated SarnautCore constant.

Every other schema now accepts an optional `curation_note`. ADR 0029 makes a
non-empty note **mandatory** on overlay documents and a missing one a compile
error; the schema cannot tell an overlay document from a base one, so it allows
the field everywhere and `sarnaut-pack` enforces the requirement where it
applies.

### Stable quest objective ids

Every quest objective carries `objective_id` in the form
`<quest-id>.objective.<64 lowercase BLAKE3 hex characters>`. The extractor does
not use the objective's array index. It hashes a sequence of UTF-8 components,
each prefixed by its byte length as an unsigned 64-bit little-endian integer:

1. `sarnaut.quest-objective.v1`, the quest id, and the objective kind;
2. `source-id` and the normalized `QuestCountId` href when the counter has one;
3. otherwise `semantic`, the normalized custom-name href, and the sorted,
   deduplicated normalized target ids or hrefs.

Reference normalization trims whitespace, changes backslashes to slashes,
removes the fragment after `#`, removes leading slashes, and lowercases ASCII.
Limits, `internal`, `show_count`, and unknown extension fields do not enter the
identity. Reordering objectives or changing those mutable properties therefore
does not orphan saved progress. Two objectives with the same derived id are an
error; the source must give them distinct `QuestCountId` resources or curation
must assign distinct ids.

`ability.schema.json` is deliberately minimal. It exists because
[ADR 0032](https://github.com/SarnautCore/docs/blob/main/adr/0032-character-creation.md)
puts `starting_abilities` on the chargen document and requires those ids to resolve.
Full ability and spell extraction is queued per ADR 0003.

`quest-script.schema.json` and `script-trigger.schema.json` carry the first
ADR 0036 script rows. The YAML node uses `key`; the pack writer maps it to
`ScriptNode.node_key`. Likewise, quest-script `quest` and counter `objective`
map to `quest_id` and `objective_index`. Each counter also carries M3-08's
stable `objective_id`; the index remains migration compatibility and a useful
diagnostic, while the ID is durable authority. References may retain an `href`
in the private YAML as provenance, but only `id` and `row_type` enter `ContentRef`.
An unknown opcode is valid. Its required tier says whether the evaluator runs,
counts without running, or refuses it.

JSON Schema enforces the ScriptValue one-member union. The separate
`check_script_contract.py` check enforces row-wide rules that draft 2020-12
cannot express: bytewise-sorted unique field names, row-owned unique node keys,
a maximum depth of 32 and no more than 4096 nodes per row.

Placement documents carry `map_resource`, the canonical product map slug, and
a `locators` list. Each locator is a non-empty `script_id` plus a global-frame
position. The compiled `MapLocator` row copies `map_resource` to `map_id`.
Its table is `map-locators.sptbl`, row type 17, and its exact row key is
`<map_id>/<script_id>`. Both key components exclude slash, backslash and
control characters. The placement contract rejects duplicate script IDs even
when their positions differ. A DestinationLocator map reference uses the same
bare product slug with `row_type: map`; the runtime never parses an `ext.*`
source-derived identifier.

## The zone-free base

`common.schema.json` holds the vocabulary every document type shares: `slug`,
`canonicalId`, `zoneId`, `locKey`, `resourceRef`, `source`, `base`, `position`,
`orientation`, `statEntry` and the recursive script definitions.

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

- A resource ref that carries an `id`. `href` alone means the
  extractor has not mapped that source path to a canonical id yet; those are
  counted and printed, never failed, because an unmapped ref is honest about
  coverage while a wrong id is not.
- A canonical id written inline in `zone`, `zone_id`, `quest`, `route`,
  `item_id` or `faction`, and every entry of `prototype_chain`,
  `starting_abilities` and `starting_quests`.
- A `QuestCountId` declared by a quest-script counter binding. M3-09 embeds
  these ids; there is no standalone quest-count-id row yet.
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
python scripts/check_placement_contract.py # map locator identity invariants
python scripts/check_script_contract.py # recursive script row invariants
python scripts/check_references.py      # dangling references and cross-field invariants
python scripts/check_negative.py        # fixtures that must be rejected
python scripts/check_proto_contract.py  # protoc compile plus locked field map
python scripts/check_no_private_data.py # clean-room guard
```

`check_proto_contract.py` requires `protoc` on `PATH`.

A demo document is routed to its schema by the first segment of its `id`, via
`SCHEMA_BY_ID_PREFIX` in `scripts/_common.py`. `validate_demo.py` fails if any
document schema has no demo document, and `check_negative.py` fails if any is
missing its `unknown-property` or `malformed-id` fixture — an uncovered schema is
one that has never been shown to accept or reject anything.

## License

AGPL-3.0. See [LICENSE](LICENSE).
