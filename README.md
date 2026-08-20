# data-schemas

JSON Schemas for SarnautCore game-design YAML + a small hand-authored demo dataset (no MY.GAMES content).

## About SarnautCore

This repository is part of SarnautCore, a fan-driven, non-commercial, open-source recreation kit for Allods Online.

The project charter and the architecture decision records live in [SarnautCore/docs](https://github.com/SarnautCore/docs). Read those before opening a pull request here.

## Clean-room posture

SarnautCore is built clean-room. This project never distributes game assets or data owned by MY.GAMES. Everything in this repository is written from scratch: the schemas describe the shape of design data, and the demo dataset is invented content used for tests and examples. Do not commit extracted or derived game data here.

## Layout

- `schemas/`: JSON Schema documents that validate the game-design YAML.
- `demo/`: a hand-authored dataset that validates against those schemas. It is
  also the source of the golden runtime pack that `server` and `client` tests
  share, so treat a change here as a change to those tests.
- `proto/`: the `sarnaut.content.v1` row messages of the compiled runtime pack
  ([ADR 0029](https://github.com/SarnautCore/docs/blob/main/adr/0029-runtime-pack-format.md)).
  JSON Schema stays authoritative for the authored YAML; these describe the
  compiled row shape. The pack writer in `tools` and the reader in `server` each
  vendor a copy of this directory for a hermetic build, and those copies must
  stay identical to it.

The extractor validates generated YAML before writing when invoked with
`--validate`. Pass `--schema-dir` explicitly or keep this repository beside the
`tools` and private `data` repositories so the CLI can find `schemas/`.

## License

AGPL-3.0. See [LICENSE](LICENSE).
