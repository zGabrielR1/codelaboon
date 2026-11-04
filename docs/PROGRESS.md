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
- **Progress**: `codelaboon doctor` and GitHub Actions workflow complete locally
- **Release**: `v0.2.0` pending tag

## Current Objective

**ACTIVE**

Stabilise codelaboon for routine use and publish `v0.2.0`.

## Shipped Features

- Provider-agnostic CLI: `providers list`, `models list`, `chat`, `configure`, `doctor`
- Providers: ChatGPT/OpenAI, NVIDIA, OpenRouter, Luna
- TOML config in `~/.config/codelaboon/providers.toml` (`0700` / `0600`)
- Source-tree and optional pip install (`pyproject.toml`, console script)
- Structural verification and offline tests

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
