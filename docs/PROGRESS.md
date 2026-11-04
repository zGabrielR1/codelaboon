# PROGRESS — codelaboon State Tracker

Done / in progress / blocked tracking; objective continuity across sessions.

## Session History

### Session 2026-11-03 — initial release

- **Objective**: Create codelaboon CLI harness for AI model access
- **Progress**: v0.1.0 shipped
- **Release**: `v0.1.0`

### Session 2026-11-03 — release stabilisation

- **Objective**: Verify from clean clones, add offline tests, prepare next tag
- **Progress**: v0.1.1 shipped
- **Release**: `v0.1.1`

### Session 2026-11-03 — diagnostics and CI

- **Objective**: Add runtime diagnostics and release automation
- **Progress**: `codelaboon doctor` and GitHub Actions workflow complete
- **Release**: `v0.2.0`

### Session 2026-11-03 — decision models

- **Objective**: Add typed decision modeling derived from the AI decision API
- **Progress**: predicate/choice/score questions, OpenAI and System One routes
- **Release**: `v0.3.0`

### Session 2026-11-04 — free model catalogue input

- **Objective**: Add the dsh-our-free-model local gateway as a model provider
- **Progress**: `ourfree` provider with the full free lane roster (DeepSeek
  first), live discovery from `GET /v1/models`, `base_url` config support
- **Release**: `v0.4.0`

### Session 2026-11-04 — terminal UI

- **Objective**: Add an interactive TUI on top of the harness
- **Progress**: Textual app with provider/model browser, multi-turn chat and
  inline doctor; optional `[tui]` extra; headless pilot tests
- **Release**: `v0.5.0`

### Session 2026-11-04 — Kilo free pool

- **Objective**: Add KiloCode's keyless free models as a provider
- **Progress**: `kilo` provider against Kilo AI's public gateway — live
  `isFree` discovery, keyless chat with SSE/JSON shape parsing, reasoning
  levels, keyless-aware CLI/TUI status
- **Release**: `v0.6.0`

## Current Objective

**ACTIVE**

Validate the `kilo` lane against the live gateway and ship `v0.6.0`.

## Shipped Features

- Provider-agnostic CLI: `providers list`, `models list`, `chat`, `decision`,
  `configure`, `doctor`, `tui`
- Optional Textual TUI: provider browser, live model catalogue, multi-turn
  chat, inline doctor (`ctrl+d`)
- Providers: ChatGPT/OpenAI, NVIDIA, OpenRouter, Luna, Our Free Model, Kilo
- Free model catalogue: every model on the dsh free lane (DeepSeek V4.1 Flash
  leads) plus Kilo's keyless `isFree` pool, both discovered live with
  offline fallback lists
- Keyless providers: `kilo` needs no credential at all; status and configure
  flows reflect that
- Typed decision questions with OpenAI `/decisions` and System One `/systemone`
- TOML config in `~/.config/codelaboon/providers.toml` (`0700` / `0600`),
  with a `base_url` override honored by every provider
- Source-tree and optional pip install (`pyproject.toml`, console script,
  `[tui]` extra)
- Structural verification and offline tests (TUI tests skip cleanly when the
  extra is absent)

## Verification

- `scripts/verify.sh` — structure, syntax, imports, no tracked secrets
- `scripts/test.sh` — mocked provider and config tests, no network
- GitHub Actions — Python 3.11, 3.12, 3.13

## Blocked / Not Done

- Production API keys have not been supplied for live endpoint validation
- GitHub Release notes may be absent unless published manually or via `gh`
- macOS/Windows CI matrix is not automated yet

## Metrics

- **Documentation completeness**: complete for current scope
- **Code completeness**: core features complete
- **Verification completeness**: structural and offline CI complete
- **Testing completeness**: unit/smoke coverage present; no live-network tests

## Dependencies

- Python 3.11+
- `requests`
- GitHub Actions (CI)
- `markdownlint-cli2` (optional linting)
