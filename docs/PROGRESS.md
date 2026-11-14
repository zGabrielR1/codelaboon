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

Validate the native source runtime release and installed artifacts; maintain the
OS-managed local routing/background worker. See the 2026-11-13 native-runtime entry.

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


## RC5 - Freebuff account sign-in - 2026-11-05

- Added `freebuff` provider: Freebuff account on the ad-funded free tier via
  device-code login (browser sign-in, token polled from the web app). No
  subscription, no credits, no API key. Free sessions are admitted per model
  for an hour; limits and withdrawn-model rejections are explained. The
  provider speaks the compiled catalog by plain wire model ids, so no catalog
  handles or device signing are needed; models that exist only in the
  server-driven catalog are not listed. Free-tier data policy applies.
- CLI `login` accepts chatgpt, claude, gemini and freebuff; `configure` starts
  account sign-in when no key is entered. TUI dialog and web action menu cover
  all four. A token from an installed Freebuff CLI, `CODEBUFF_API_KEY` /
  `FREEBUFF_API_KEY`, or an explicit `[freebuff]` token is honored without a
  new browser sign-in.
- 100 offline tests pass, including new Freebuff auth, provider and session
  coverage. Live authorization and inference remain unverified without real
  accounts.

### Session 2026-11-08 — RC8 release hardening

- Added WusRouter, native Qoder Cloud Agents and TUI account-key setup.
- Added a responsive whale ASCII welcome screen.
- Review found interrupted-config-write risk, lost concurrent config updates,
  stale busy/model state after key changes and malformed/recoverable stream
  handling. Added fixes and targeted regression tests.
- Repaired Makefile's obsolete `docs/CURRENTTASK` check and included workflow
  files in the source archive for structural verification from releases.
- Build RC8 locally with checksums; validate wheel installation and source
  archive before marking it ready. No authenticated inference claim.
- Future runs: test source archives as well as source checkouts, and isolate
  local credential discovery in tests that assume an unconfigured account.

- RC8 validation: 132 extracted-source tests pass. Empty archival directories
  are no longer required by structural verification. Review confirms config
  replacement failures preserve the original, concurrent updates survive,
  account changes invalidate old chat generations, and partial/failed cloud
  streams cannot be reported as successful turns. Live authentication and
  remote resource/credit behavior remain the next validation objective.

### Session 2026-11-13 — local orchestration and cloud workers

- Added a persistent command scheduler, loopback-only Qwen routing adapter,
  Codelaboon cloud planner adapter, OpenCode cloud builder adapter and background
  supervisor. The local model receives routing metadata only. Planning and
  implementation run through explicit cloud workers; configured acceptance
  commands decide completion. Failure pauses/cools workers without local coding
  or a paid fallback.
- Downloaded and checksum-verified llama.cpp b12360 and official Qwen3 0.6B Q8
  into gitignored `.watch/local`. Real local routing and free cloud inference
  succeeded. Both isolated smoke projects completed planning, implementation
  and independent acceptance commands.
- Nine focused scheduler/routing/cloud-worker tests pass. The wider 139-test
  run had 2 failures and 15 errors in existing auth/UI tests (JWT module shape,
  mocked Windows home handling, POSIX permission expectations and `/tmp` output).
  All structural checks pass. Git Bash initially lacked `python3`; a local
  gitignored shim to the installed Python plus UTF-8 mode allowed the unchanged
  verification script to complete. Direct new-module syntax compilation passes.
- Prepared an isolated snapshot of the user-selected DigiSat recomp tooling,
  with explicit source provenance and baseline copies. The cloud-authored plan
  targets lost build manifests on compiler timeouts/launch failures. Before the
  change, an independent three-case offline oracle confirmed two failures and
  one success. The cloud implementation completed; all three independent
  oracle checks and all six cloud-authored offline tests pass. Both the original
  snapshot file hashes and the reviewable patch are checked before delivery.
  `.watch/artifacts/digisat-recomp-build-manifest.patch` contains the isolated
  source-tooling change. No original checkout or installed binaries were changed.
- Adversarial review: success alone cannot establish behavioral equivalence;
  the oracle specifically tests handled failures, dependent-job suppression,
  manifest invariants and command flags. Added cloud tests were run separately
  to avoid accepting implementation output with a broken test suite. Runtime
  claims are limited to the running supervisor and completed finite queue;
  cloud limits, logout, OS events and hardware failure still apply.
- Future runs: use `python -m codelaboon.service .watch/watch-active.json
  --background` for the selected project queue; PowerShell script policy may
  disable the optional `.ps1` launcher. Do not clear real provider cooldowns.
  The initial local encoding failures were corrected by emitting UTF-8; their
  diagnostic records remain in the attempt history.

### Background worker controls — 2026-11-13

- Added `codelaboon work`: interactive control menu plus start, stop, status,
  pause, resume, logs and add commands. The commands dispatch before provider
  configuration is loaded. Closing the menu leaves the service running.
- Added atomic task inbox files polled between attempts. Instructions added
  while running require no restart and keep existing plans/completed IDs.
  Each new task requires explicit acceptance commands; it does not interrupt
  or inject a live message into the current cloud agent.
- Native llama-server/OpenCode discovery now distinguishes Windows and POSIX.
  The setup helper downloads the model alone on POSIX and asks for a native
  runtime instead of downloading a Windows executable there. Linux/macOS
  execution remains unverified here; DigiSat native tasks still need Windows.
- Thirteen focused control/scheduler/router/cloud-worker tests pass, including
  an instruction arriving during an active supervisor run and pause/resume.
  Tested real Windows status and graceful stop; restarting the background
  service preserves the three completed project tasks. Source syntax checks pass.
- Review: service presence uses the OS lock rather than trusting stale PID files;
  status labels old unfinished attempts as active or interrupted. No auto-start
  after reboot is installed. CLI shell-like command parsing supports --checks-json
  when exact Windows arguments are required. Normal default launch still opens
  the chat TUI; `work` is the dedicated worker control entry point.

### Session 2026-11-13 — CLI-TUI-first, free (Auto), install and project root

- Reframed the product as a CLI-TUI-first coding agent: `codelaboon` with no
  command opens the terminal workspace, in the interaction style of Claude
  Code, OpenCode, Codex CLI and Pi. README now states that CLI-first means a
  CLI TUI and documents the composer, searchable pickers, session rail and
  project root.
- Added `free (Auto)` as the TUI/CLI default. It is a synthetic provider
  (`codelaboon/free_auto.py`) that ranks configured free lanes by availability
  (55%), intelligence (30%) and speed (15%), shows the lane it would use, and
  fails over at send time. `chat free free` and `models list free` expose it
  from the plain CLI.
- Fixed keyboard navigation: provider/model pickers now handle Up/Down and
  PageUp/PageDown as screen bindings, since Input does not consume them. Up/
  Down in the composer recalls previous prompts for editing and resending.
- Rewrote ChatGPT sign-in: persist the issued `oaiapp_...` client id before
  token exchange, send the documented Accept/User-Agent/Originator headers,
  tolerate a missing `scope` by reading access-token claims, and surface the
  real OAuth error code in the dialog instead of a generic failure.
- Added `codelaboon install` plus `scripts/install.sh` and `scripts/install.ps1`.
  It installs the package for the current user and idempotently adds pip's
  user script directory to PATH (Windows user registry + WM_SETTINGCHANGE;
  POSIX shell profiles). `--editable` and `--no-path` are supported.
- The process working directory is now the session project root. The TUI
  header, sidebar, `/project` and saved session metadata all show it.
- Updated TUI tests for arrow navigation, prompt recall and login-error display;
  added ranked/failover tests for `free (Auto)`. 16 focused tests pass.
- Added the keyless `pollinations` provider (live discovery, OpenAI-compatible
  chat, optional bearer token, one transient-timeout retry). It joins
  `free (Auto)`; live `chat pollinations openai-fast` and `chat free free`
  both succeeded, with Auto selecting Pollinations when Kilo returned empty.
- Verified Gemini and Claude: 31 provider/auth tests pass, `doctor` reports
  both importable, and no-catalogue handling is clean when unconfigured. Fixed
  config-directory resolution to honor `CODELABOON_CONFIG_DIR` without eagerly
  evaluating `Path.home()`; auth tests now run with a cleared environment.
  POSIX permission assertions are conditional on `os.name == "posix"`.
  Live account inference still needs real Google/Anthropic credentials.

### Session 2026-11-13 — restored native runtimes and OS-managed orchestration

- Restored pinned OpenCode and OMP clones plus the official Our Free Model
  source. Imported runtime workspaces, preserved upstream executable modes,
  pinned revision checks, licenses and original/modified file hashes. Exported
  reproducible patches and packaged source bundles for installation.
- Replaced the default launch with actual OpenCode source execution, explicitly
  loading Solid's renderer preload when the project differs from the runtime
  directory. Source runs retain the pinned version for compatible plugin loading;
  the compile-only libc symbol now has a source-safe watcher fallback.
- Added native whale branding, OMP activity frames, delegated child sessions and
  live worker status in the sidebar. Verified native theme selection and Up-arrow
  recall in a real tmux terminal with a local fixture provider.
- Added loopback transport preserving chat/Responses/Anthropic/Google tools and
  streams, Gemini account envelopes and Freebuff admission metadata. Added local,
  OpenRouter-free, Groq and Cerebras providers; native Auto rotates compatible free
  lanes. API-key Gemini and Qoder Cloud PATs cannot enter free Auto. Qoder PATs
  always use HTTP even when an optional CLI is present. Added redacted catalogue
  checks and official standalone Our Free Model setup/start/connect commands.
- Added local-only inference and a packaged authorized-pentesting profile. Small
  local context budgets have reduced compaction reserves. Local inference ignores
  proxies and redirects; local-only routing does not sandbox tool networking.
- Improved virtualenv/externally-managed Python installation, Fish PATH syntax,
  piped shell/PowerShell bootstraps, runtime/Bun setup and failed-pull behavior.
- Added systemd user/Scheduled Task/LaunchAgent registration, empty persistent
  queues, worker availability probes and health/timing routing metadata. Background
  builders use the source runtime, with no external OpenCode binary requirement.
- Linux service is enabled and running, with lingering enabled after logout.
  `.runtime/work.json` is a separate empty queue; the legacy `.watch` data was
  preserved. A real local Qwen routing request returned a valid candidate.
- Validation: 176 Python tests; structure/syntax and shell syntax; OpenCode
  typecheck; OMP check:ts (Biome + types); actual file-tool round trips for both
  engines using local fixture models. Wheel/source packages carry the fork sources
  and patches while excluding secrets, dependencies, runtime state and model weights.
- Adversarial review addressed source-vs-project renderer setup, version drift,
  compile-only globals, local proxy leakage, paid route exclusion, wire-level tool
  preservation, interrupted extraction, source-mode preservation and stale installer
  assertions. Tests distinguish catalogue visibility from inference eligibility.
- Remaining environment checks: Windows/macOS service execution and real
  Claude/Gemini/Qoder inference. Existing ChatGPT/Freebuff sessions expose model
  listings; no quota claim follows. No remote publication or commits were made.
- Future runs: read docs/native-runtime.md and CURRENTTASK. Keep the service idle
  until concrete tasks with checks are queued. Build source archives after changing
  any fork patch, and verify installed artifacts outside the checkout.

### Session 2026-11-13 — RC10 native UI verification and publishing

- Inspected Kilo CLI revision 85eb887a7560f452211bcd382eafe8cb2f8df497. It confirms
  the upstream-fork pattern: shared native UI with theme/extension additions.
  Kept both source renderers/editors intact and added the exact native Kilo theme,
  OMP native palette adaptations and preserved license/revision/hash provenance.
- Added a native --theme launch option while respecting saved selections.
  Fixed OMP config-root resolution for absolute profile paths and contained its
  sessions/logs/themes in the Codelaboon profile. Used native condensed changelog
  and binary-update-check defaults instead of replacing the welcome component.
- Added repeatable real tmux checks for both engines at 80/160 columns: welcome,
  fixture response, prompt recall, native theme/settings menus, wide OpenCode
  delegated/background sidebar and OMP profile-local logs/session persistence.
  Shared the fixture server with the existing actual file-tool round-trip checks.
- Added replay-checked patch export, complete bundle hash verification, and a
  reusable native CI matrix. GitHub release publication now waits for native UI,
  native types/tools, Python and source/tag checks before publishing artifacts.
- 178 Python tests pass locally; native type checks and all four terminal cases
  pass. No cloud inference quota is inferred from these fixture checks. Publishing
  status is tracked by the v1.0.0-rc.10 tag workflow/release page.
- Future runs: retain upstream renderers and minimize UI patches. Run smoke_ui.py
  --setup --types from a source artifact to exercise the same path as CI. Read
  docs/release-1.0.0rc10.md for source revisions, coverage and environment limits.


### Session 2026-11-14 — RC11 Fedora startup repair

- Fixed normal OpenCode startup stalls; bounded provider discovery and cached
  metadata, skipped duplicate empty plugin installs, unified setup/cache paths.
- Production dependencies, optional Textual, automatic verified Bun without npm.
- Added official optional Kilo/Claude native engines; preserved working OMP.
- 183 tests, OpenCode types, bundle/structure checks, installed default UI,
  OMP/Kilo native UI/tool checks, Claude onboarding and standalone Bun bootstrap.
- Lesson: local-only UI checks missed the normal startup defect. CI now tests the
  installed normal path from a fresh profile and optional native Kilo tools.
- Publication target: v1.0.0-rc.11; remote workflow is the publication authority.

- Published [RC11](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.11)
  from `e4e11eb`: release run `43555456667`, verify run `43555456805`, all
  native UI/tool gates successful. Downloaded wheel/sdist checksums verified.


### Session 2026-11-14 — RC12 VTE blank-screen race

- Reproduced blank OpenCode in actual VTE (Fedora default Ptyxis/GNOME Terminal),
  alongside a working alternate-screen control. Plain PTY and tmux masked it.
- Fast OSC 11 reply let frontend RPC requests precede the worker listener; added
  readiness handshake, awaited calls and bounded startup wait.
- RC11 fails new immediate-reply regression; installed RC12 passes real VTE UI,
  response and prompt recall, tmux/theme/sidebar checks, types and 183 unit tests.
- Added actual VTE/Xvfb CI gate and portable immediate-reply regression.
- Next: publish v1.0.0-rc.12 only after CI succeeds. Preserve user profiles/queues.

- User confirmed installed RC12 opens in a fresh Ptyxis window ("Yes, it opens").
- Published [RC12](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.12)
  from `99eb59f`; release `43612181195` and verify `43612181008` succeeded,
  including actual VTE/Xvfb. Downloaded release wheel/sdist hashes verified.


### Session 2026-11-14 — RC13 Claude Code free backend

- Native Claude Code now defaults to free (Auto) with an isolated profile,
  preconfigured onboarding and free-only model picker; no Anthropic subscription.
- Added dependency-free Messages/Chat adapter with streaming/tools/usage/errors.
  Kept trust/permissions; excluded personal Claude credentials from this route.
- 191 tests, native UI/picker and Read tool round trip without Anthropic account,
  plus a successful live free-provider reply. Added native Claude CI gates.
- Next: install and publish reviewed RC13 only after complete CI succeeds.

- Installed RC13 wheel locally; user confirmed native Claude opens on free without
  account login ("Yes, it opens on free").

- Published [RC13](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.13)
  from `2c4fbcd`: release run `43614265583` and verify run `43614265809` succeeded,
  including native Claude UI/tools and all existing engine/VTE gates. Downloaded
  wheel/source checksums verified. User acceptance confirmed; requested RC complete.


### Session 2026-11-14 — RC14 Crush engine

- Added optional official Crush v0.101.0 native engine with verified download,
  free gateway/picker, isolated project state, native themes and local/security modes.
- Kept interactive mode in-process; scoped native headless server to each run to
  fix reproduced fast-reply stdout loss. Readiness/cleanup have regression coverage.
- 200 tests, repeated file-tool loops, actual UI/history/themes/session DB, installed
  Fedora VTE and live free-provider response pass. User confirmed Ptyxis startup.
- Added Crush UI/tool/VTE CI gates. No new runtime dependencies; upstream FSL
  license retained. Next: publish reviewed RC14 only after CI succeeds.

- Published [RC14](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.14)
  from `ed67452`; release `43620769354` and verify `43620769150` succeeded, including
  native Crush UI/tools/VTE and all existing engines. Downloaded wheel/source
  checksums verified. Installed user acceptance confirmed; requested RC complete.
