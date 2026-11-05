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


## Local workspace update ? 2026-11-05

- Default command launches TUI; Textual is a core dependency.
- Added loopback web workspace with provider discovery, persisted conversations, export, theme switch, and responsive layout.
- Added original whale/code-bracket SVG logo.
- API tests cover discovery/chat, origin/host/token rejection, input validation and error redaction.
- Browser QA blocked by unavailable browser access host; live provider chat is not verified.


## ChatGPT catalogue and sign-in ? 2026-11-05

- Removed synthetic GPT-3.5/GPT-4 access tests and hard-coded default roster.
- Added public OSS ChatGPT registration with PKCE, callback state, JWT signature/issuer/audience/expiry/nonce checks, atomic credential writes and refresh rotation.
- Added CLI login and web Continue with ChatGPT, current account catalogue and display names, completed-only Responses stream handling.
- API credentials take precedence and subscription tokens are restricted to the official endpoint.
- Offline tests cover catalogue shape/order/visibility, stream errors, token refresh and identity validation.
- Real OAuth authorization/account catalogue and browser UI remain unverified; user must complete sign-in.


## Integrated terminal sign-in and OpenCode layout ? 2026-11-05

- Inspected local OpenCode home and session sidebar source.
- Replaced persistent left catalogue with searchable modal pickers and a right context sidebar.
- Added centered home composer, slash commands, narrow-terminal sidebar behavior, and in-TUI ChatGPT sign-in with background worker.
- Sign-in progress uses UI notifications rather than printing over the terminal.
- Verified 55 offline tests including login dialog dismissal, login completion refresh, provider search, sidebar shortcut, and home reset.
- Real browser authorization and interactive visual inspection remain unverified. This is a Textual implementation of the main layout, not a complete OpenTUI feature port.


## RC2 ? 2026-11-05

TUI session persistence/resume/export; browser draft recovery, search, rename, reversible archive and stop-waiting. Discovery generations and busy-prompt preservation fixed. 60 tests pass; browser fixture checks pass at desktop/mobile sizes. See release-1.0.0rc2.md for evidence and limitations.


## Taste framework rework ? 2026-11-05

Data terminal direction applied to web shell, typography, starter rows, action menu and TUI palette. Browser checked 1440/768/390, source lint clean, 60 tests pass. Framework CDP inspector timed out; fallback browser evidence recorded in visual-rework.md.


## RC4 - Claude and Gemini account sign-in - 2026-11-05

- Added `claude` provider: Anthropic Messages API with an API key, plus the
  public Claude Code OAuth PKCE flow for claude.ai plans. Free claude.ai
  accounts can connect, but Anthropic currently grants no Claude Code/API
  inference on the free plan; the provider surfaces the provider's own error.
- Added `gemini` provider: Google AI Studio API key, plus Google account OAuth
  with automatic free Code Assist onboarding. This is the explicit
  free-as-in-beer account lane; the free-tier data policy is documented. The
  OAuth client is user-supplied and stored privately, so no client credentials
  are embedded in the repository.
- CLI `login` accepts chatgpt, claude and gemini; `configure` starts account
  sign-in when no key is entered. TUI dialog and web action menu cover all three.
- Account sessions are atomic/private, refresh automatically, and are refused
  for custom base URLs. Pinned fallback rosters cover discovery failures.
- 86 offline tests pass, including new Claude/Gemini auth, provider and web
  coverage. Live OAuth authorization and inference remain unverified without
  real accounts; the provider decides what each plan or free tier includes.
