# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.2.0] - 2026-11-03

### Added

- `codelaboon doctor` diagnoses Python version, dependencies, provider imports,
  configuration path/permissions, tracked credential files and source docs.
- `scripts/test.sh` offline unit and smoke tests, including a doctor check.
- GitHub Actions workflow (`.github/workflows/verify.yml`) running tests and
  structural verification on Python 3.11, 3.12 and 3.13.

### Changed

- Release tracking (`CURRENTTASK`, `docs/PROGRESS.md`) now reflects shipped
  releases through v0.2.0.
- Historical verification report is marked as such.

## [0.1.1] - 2026-11-03

### Added

- Offline unit and smoke tests in `tests/test_codelaboon.py`, plus
  `scripts/test.sh` and a `make test` target.
- `scripts/verify.sh` now checks that the test runner and test file exist.

### Changed

- `CODELABOON_CONFIG_DIR` is now honoured by the CLI as well as the
  configuration module, so tests and alternate setups no longer write to the
  real home configuration directory.
- Updated stale dependency/requirements statements in the summary and
  architecture docs to match the stdlib `tomllib` implementation.

## [0.1.0] - 2026-11-03

### Added

- Initial public source release of the codelaboon CLI harness.
- Provider-agnostic command structure: `providers list`, `models list`, `chat`,
  and interactive `configure`.
- Providers: ChatGPT/OpenAI, NVIDIA, OpenRouter and Luna, built on a shared
  `BaseProvider` contract in `providers/base.py`.
- TOML-based configuration in `~/.config/codelaboon/providers.toml`, created
  with restrictive permissions (`0700` dir / `0600` file) on first run.
- `config/providers.toml.example` as a safe template; real keys are never
  committed.
- `scripts/verify.sh` and Makefile verification targets for structure, syntax,
  and imports.
- Project documentation under `docs/` (architecture, agents, workflow).

### Fixed

- Replaced the unmaintained `toml` dependency with the standard-library
  `tomllib` reader plus a small TOML writer.
- Fixed the `chat` command joining message dicts instead of sending the
  prompt text, and wired the `--system` flag through correctly.
- Fixed the Makefile syntax error that prevented `make check` from parsing,
  including the broken `docs/PROGRESS.md` test and the `test-providers`
  recipe.
- Removed the unused `sys.path` hack in `codelaboon/cli.py` and made imports
  work both from a source checkout and when installed.

### Security

- Configuration directory and file are created with owner-only permissions.
- `config/providers.toml` and `config/api_keys.toml` are gitignored; only the
  example template is tracked.
