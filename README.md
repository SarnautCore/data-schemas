# data-schemas

JSON Schemas for SarnautCore game-design YAML + a small hand-authored demo dataset (no MY.GAMES content).

## About SarnautCore

This repository is part of SarnautCore, a fan-driven, non-commercial, open-source recreation kit for Allods Online.

The project charter and the architecture decision records live in [SarnautCore/docs](https://github.com/SarnautCore/docs). Read those before opening a pull request here.

## Clean-room posture

SarnautCore is built clean-room. This project never distributes game assets or data owned by MY.GAMES. Everything in this repository is written from scratch: the schemas describe the shape of design data, and the demo dataset is invented content used for tests and examples. Do not commit extracted or derived game data here.

## Layout

- `schemas/`: JSON Schema documents that validate the game-design YAML.
- `demo/`: a hand-authored dataset that validates against those schemas.

The extractor validates generated YAML before writing when invoked with
`--validate`. Pass `--schema-dir` explicitly or keep this repository beside the
`tools` and private `data` repositories so the CLI can find `schemas/`.

## License

AGPL-3.0. See [LICENSE](LICENSE).
