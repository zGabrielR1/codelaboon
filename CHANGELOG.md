## 1.0.0rc1 ? 2026-11-05

- Default terminal workspace with searchable provider/model dialogs, right session sidebar, slash commands and integrated ChatGPT sign-in.
- Loopback web workspace with local conversation persistence, model discovery, export, code blocks, responsive layout and theme selection.
- ChatGPT public OSS authorization with PKCE, verified identity tokens, token refresh, live account catalogue and Responses inference.
- Stale chat-result guards, error recovery, request timeouts and localhost origin/token checks.
- Original vector whale/code logo; web assets included in wheel and source distribution.
- Verified offline suite and browser fixture flows. Live ChatGPT authorization, subscription inference and cross-platform CI execution remain unverified.

# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.6.0] - 2026-11-04

### Added

- `kilo` provider: Kilo AI's public gateway free pool as a keyless model
  catalogue input — no account, no API key, no fingerprint gate.
- Live discovery: `models list kilo` keeps only the listing's `isFree` slice;
  the auto-routers `kilo-auto/free` and `openrouter/free` are the offline
  fallback roster.
- Stream-shaped parsing: chat asks for SSE and folds `data:` deltas by shape,
  skipping `: KILO PROCESSING` keepalives, and accepts a single JSON document
  when the gateway answers non-streamed; error frames surface as API errors.
- `reasoning` levels (`off`, `low`, `medium`, `high`) mapped onto the
  gateway's `reasoning` field (`{"enabled": false}` for off).
- Keyless providers: `BaseProvider.keyless`; `providers list` reports
  "Free (no key needed)" and `configure kilo` offers only a base URL override.

## [0.5.0] - 2026-11-04

### Added

- `codelaboon tui`: an interactive terminal UI built on Textual — provider
  browser with configured status, model catalogue (refreshed live, so the
  `ourfree` roster tracks the gateway), multi-turn chat with context reset on
  provider/model switch, and `ctrl+d` inline diagnostics.
- `tui` optional extra: `pip install 'codelaboon[tui]'`; the core harness
  stays `requests`-only and the command prints install instructions (exit 2)
  when the extra is absent.

### Changed

- CI now installs `textual` so the headless TUI pilot tests run on the
  Python 3.11–3.13 matrix; tests skip cleanly when the extra is missing.

## [0.4.0] - 2026-11-04

### Added

- `ourfree` provider: the dsh-our-free-model local forward gateway is now an
  input to the model catalogue. Its models are all free (DeepSeek V4.1 Flash
  and V4 Flash lead the list, then GLM 5.3 Flash, MiMo, Nemotron, Ling,
  Space Bunny, Union Alpha, Muse Spark and Jev).
- Live model discovery: `models list ourfree` fetches the roster from the
  gateway's `GET /v1/models`, so the catalogue follows the upstream refresh;
  configured models are the offline fallback.
- `base_url` key in `providers.toml` (honored for every provider) to point at
  a forward gateway that moved off its default port.
- `codelaboon configure ourfree` now asks for the gateway base URL, defaulting
  to `http://127.0.0.1:18899/v1` and preserving an existing value.

## [0.3.0] - 2026-11-03

### Added

- Typed decision models: `codelaboon decision <provider> <model> <input>` asks
  `predicate`, `choice` and `score` questions and prints probability-bearing
  answers as text or `--json`.
- Two decision wire protocols:
  - OpenAI `/v1/decisions` (ChatGPT provider)
  - System One `/systemone` (OpenRouter provider)
- Inline question syntax and JSON question files (`--questions`), with
  validation for unique names, choice values and score levels.
- `docs/DECISIONS.md` and `examples/questions.json`.

### Fixed

- `chat` and `decision` now exit non-zero when the provider is missing,
  unsupported, unconfigured or the request fails.

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
