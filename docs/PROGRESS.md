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

### Session 2026-11-14 — RC15 lean storage and lightweight swarms

- User chose OpenCode UI with lightweight swarm/background execution. Kept the
  working UI and all prior optional engines; added verified native Jcode v0.99.1.
- Core distributions now carry a pinned asset manifest; OpenCode/OMP bundles
  publish separately. First-use dependencies are automatic; prefetch is optional.
- Moved bulk development trees, references, release copies, local weights and
  history outside ppp without deletion. Checkout measured 3.9 GB → 29 MB; initial
  thin wheel 173 KiB. Preserved the three legacy tasks in external legacy history.
- Restarted the empty background service with canonical state and rewritten local
  model paths. Idle service measured ~35 MiB with model unloaded; work reloads it.
- Native two-worker file reads/reports and hard-cap rejection pass. Default
  background builders now use Rust, with independent supervisor verification.
- Added storage/checksum/lifecycle/acceptance regressions, thin-package CI guard,
  native swarm CI, documentation and RC15 adversarial review. Actual OpenCode VTE
  rendering/reply/Up recall and file-tool gateway checks pass after relocation.
- Next: final build/reinstall and 208-test run, then commit/tag/publish only after
  complete native release gates. Do not claim upstream RAM ratios as our results.

- Published [RC15](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.15)
  from `db3bb97`. Verify `43629827877` and release `43629831664` both succeeded,
  including all native UI, VTE, optional engines, Rust swarm/cap and build gates.
  Verified every published SHA-256; installed the exact published 177843-byte
  wheel. Source distribution 293190 bytes. Real cold OpenCode/OMP HTTP downloads
  succeeded from the installed thin package with an empty temporary cache.
  Requested RC complete; await user feedback. No user data deleted.


### Session 2026-11-14 — RC16 continuous swarms and native Jcode UI

- Connected native swarms to the existing durable supervisor. Added continuous
  local-model or worker control, successful cycle limits, due times/backoff,
  independent verification budgets and per-objective pause/resume/stop/status.
- Kept worker-controlled jobs independent of the local router. Shared readiness
  rules unload idle models and preserve scheduler fairness during local outages.
  Added bounded prior progress for plain planners and native coordinators.
- Completed Jcode as an interactive engine: stable project profiles, display
  preferences, native session resume, unlimited interactive lifetime and owned
  native server cleanup. Default UI remains OpenCode.
- Fixed skipped verification in plain queued tasks and literal command arguments.
  Added supervisor feature detection before enqueueing on an old live process;
  TERM/HUP cleanup unwinds owned child groups.
- 223 unit tests pass in external development environment. Native Jcode UI reply,
  session resume/server exit, two real swarm cycles across supervisor reload and
  an actual background service with CLI pause/resume/status/checks all pass.
- Installed local RC16 and restarted only the confirmed-empty user service.
  Actual installed OpenCode VTE rendering/reply/Up recall passes. Core wheel
  remains below180KiB; source checkout stays29MB, with no new runtime dependency.
- Reviewed docs/review-1.0.0rc16.md. Next: commit/tag/publish RC16, wait for complete
  native gates, verify release checksums/cold assets, then install published wheel.
  No real user work objective has been queued or started by this session.

- Published [RC16](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.16)
  from `3284c87f2801c9202275d1df183d42fedc386bc7`. Verify `43642855045` and
  release `43642857338` succeeded, including all new native UI/background gates.
  Verified every published SHA-256 and installed the exact 183654-byte wheel.
  Cold OpenCode/OMP HTTP downloads from the installed RC16 manifest passed.
  User service restarted idle, with continuous-swarm capabilities and autostart
  still enabled. Checkout measures about30MB after the new commit/build.
  Requested RC complete. No real user objective was queued or started.


## RC17 — free-model verification and editor connector

- Replaced static free picker claims with endpoint/account-scoped chat and tool
  verification, live catalogs, negative quarantine and bounded background probes.
  Explicit checks stream progress and respect rate-limit retry windows. Nightly
  monitoring reports outages separately from release correctness.
- Expanded Kilo live free discovery, constrained OpenRouter routing to zero-price
  models, and added Z.AI with official free-pricing verification. LLM7 excluded
  after its live catalog showed no zero-priced models. Live Kilo Auto/Nemotron
  chat/tool receipts passed; unavailable/deferred/unconfigured routes stay explicit.
- Added a tiny VS Code connector using the official Claude Code process wrapper,
  preserving SDK tools/context/permissions. Backend settings live in private
  temporary files; no upstream credentials copied into editor configuration.
  Supports health checks and native engine terminals, with settings restoration.
- 249 Python tests, Node connector contract, HTTP health smoke, native SDK Read,
  actual official VS Code prompt/reply, and installed OpenCode VTE checks pass.
  Wheel199354bytes; source353251bytes. Source checkout stays lean, no runtime
  dependencies added. RC17 core/connector installed; idle service restarted.
- Adversarial review: docs/review-1.0.0rc17.md. Next: publish RC17 only after
  full native CI, verify published checksums/assets and install exact wheel.

- RC17 published successfully from a045fab7e937bb621a7b0e90189c24117e939a8f.
  Release43668831579 passed all native gates; published checksums verified.

## RC18 — Codex native engine and VS Code

- Added Codex CLI/app-server wrapper and Responses adapter for free chat lanes,
  including native function/custom tools and tool results. Isolated profile and
  private temporary verified model catalog; automatic pinned native setup.
- Added restorable official Codex VS Code CLI connection, Open/Disconnect commands
  and optional engine terminal. Upstream CLI hook marked development-only; reload
  required after switching an existing app-server. Actual editor prompt/reply and
  native CLI shell/file result pass. 249 regressions, Node contract and three
  focused adapter tests pass. Review docs/review-1.0.0rc18.md before commit.
- User requested focused validation and publication. Next: install local RC18
  connector/core, push tag, finish existing release CI and verify published assets.

- Published RC18 from f1eda6c. Verify43669720894 and release43669721302 succeeded,
  including optional native Codex download and real shell-tool inference. All
  uploaded SHA256SUMS entries verified; public VSIX has no local bootstrap. Exact
  published204545-byte wheel installed. Sourcecheckout remains31MB.
  Official Codex extension and connector installed locally; existing personal
  VS Code windows need reload to activate the updated connector. No editor
  windows forcibly closed. Requested RC complete; no user task queued.


## Universal sessions — RC19 development build

- Added a private compressed SQLite session library with stable IDs, native
  projection bindings and original-record archives. Codelaboon-owned native
  profiles synchronize on gateway close and explicit list/sync; unchanged files
  and SQLite WAL states are skipped. Standalone source homes remain opt-in.
- Added sessions import/export/convert/resume for OpenCode, Kilo, Codex, Claude,
  OMP, Jcode and Crush. Conversion does not open the library or perform inference;
  destination native files can be used without Codelaboon. Existing source files
  and auth profiles remain unchanged. Exports refuse overwrite.
- Native headless tests resumed the earlier conversation in all seven engines.
  Actual Codex-to-OpenCode continuation retained one universal ID and all source
  bindings. Ten focused unit cases cover formats, inert tool/policy history,
  archives, private output, active branches, compaction tails, linked prefixes,
  no-library conversion and unchanged-file caching. Full suite262 passes,
  including one concurrent user's explicit OpenCode alias test.
- Review docs/review-universal-sessions.md. Instructions/limits are documented
  in docs/universal-sessions.md. Fixed Jcode headless --resume profile selection.
- This turn requested the feature, not another publication. Installed local
  1.0.0rc19.dev0; no RC19 release/tag/commit. Preserve concurrent unrelated
  README/CLI OpenCode alias and test edits. RC18 remains the published release.


## RC19 — shared-session controls and publication

- User requested publication and Import/Export buttons for all agents. Added a
  Codelaboon Sessions activity-bar view with visible Import/Export/Convert/Refresh
  buttons, per-session Export and engine-selected Resume in native terminals.
- JSON listing backs the view; actions use direct CLI argument arrays, preserve
  cancellation, support paths with spaces and never register independent converts
  in the library. Active child cleanup and bounded output keep the host lean.
- 263 Python tests and Node button/connector tests pass. All seven native adapters
  were tested in the implementation; fresh shared-ID continuation passes. Core
  wheel217811bytes, publicVSIX includes JS/SVG with no personal bootstrap.
- RC19 core and connector installed locally. Review docs/review-universal-sessions.md
  updated before commit. Existing explicit OpenCode alias/test carried unchanged.
- Next: tag/publish RC19, wait existing release gates, verify published checksums
  and install exact wheel. Existing editor windows need reload for the new view.

- Published RC19 from 6f80122. Verify43674208542 and release43674208611 both
  succeeded, including native import/resume across seven adapters and shared-ID
  continuation. Real isolated VS Code host loaded the Sessions view/commands and
  completed Codex editor inference. All published SHA256SUMS entries verified.
- Installed the exact published218383-byte wheel and refreshed the local connector.
  Public9181-byte VSIX contains Import/Export view buttons and no local bootstrap.
  Idle worker had zero pending/completed tasks; restart on RC19 authorized.
  Existing editor windows require reload to activate the new Sessions sidebar.
  Requested release complete; no real user objective was queued.


## Audit and local RC20 development — continuous policy/scope controls

- Live RC19 service active/idle, no tasks. Local router intentionally unloaded
  while idle; runtime/model present. Isolated actual inference measured~1.4s cold
  start/~1s route selection. Routing is still heuristic, not optimal/task-aware.
- Added explicit per-task default/full permissions, coding/security profiles and
  required security scope. Native full flags never grant OS/root privileges.
  Flagged Jcode headless security injection fixed; swarm security propagated.
- Active local scope review monitors logs/Git metadata, stops/replans drifting
  work, pauses on observed path violations or failed review, and checks final
  completion. Operator controls are durable task files; old services cannot
  silently accept unsupported policy tasks. Worker-controlled mode preserved.
- 275 regression cases, native Codex/Jcode disposable permission/profile tools,
  and basic real local-model scope examples pass. Initial weak review behavior
  improved with examples/grounded evidence; complex judgment not benchmarked.
- Review docs/review-continuous-supervision.md, usage docs/continuous-supervision.md.
  Install local1.0.0rc20.dev0 and restart confirmed-idle service. No public release
  or real user work queued. Outstanding: measured task-aware routing, stronger
  controller evaluation, interactive Jcode security parity and per-tool scope gates.

- Local1.0.0rc20.dev0 installed from the built wheel; confirmed-idle service
  restarted. Installed/running versions match and advertise task-execution-policy
  plus active-supervision. Live status remains0pending/0completed; no full-access
  task was queued. Public RC19 is unchanged. New controls are CLI options only.

## RC20 public release preparation — 2026-11-15

- User authorized public RC20 and actual evaluated security workflows plus explicit
  root/admin cases across Linux/macOS/Windows. Implemented separate interactive
  native OS grants with exact argv/scope/hash/expiry/timeout and single-use receipts.
  Background worker never self-elevates. Privileged cycles need fresh case approval.
- Added bounded scoped HTTP/TLS/exposure assessments, evidence/remediation output,
  optional tool capability detection and nmap host/port scope adapters/import.
  Real vulnerable/hardened HTTP, self-signed TLS and malicious XML labs pass.
- Task-aware routing now learns from private bounded latency/acceptance observations,
  with fast/balanced/deep choices. No best-model intelligence guarantee asserted.
- Local controller regression suite records model/suite hashes, 11/13 passes,
  zero false interventions and two misses. Deterministic file guard separately
  handles staged files/reversions/inspection failures. Native Jcode security
  overlay now works in actual UI; saved session and owned process cleanup pass.
- Offline doctor/VS Code Diagnostics view added. 295 tests and structural checks
  passed; final telemetry edge-case refinement awaits final tests/build. Portable
  platform CI/native bootstrap gates added. Review in review-continuous-supervision.md.
- Version1.0.0rc20 / connector1.0.20 prepared. Public tag not pushed yet. No real
  user objective, target scan, root/admin case or model-provider spend queued.

- Final local gates:296 tests pass, structural/provenance verification passes,
  all three Node connector/button/diagnostics contract suites pass. Final core
  wheel246357B and source427534B both below1MiB; connector includes diagnostics.
  Native Jcode security UI/resume and full Codex/Jcode tool checks passed. Public
  release still pending CI; no privileged host case or real task was run.

- CI43758666288 passed portable Linux/macOS/Windows contracts and native POSIX
  root bootstrap/worker; UAC parsing passed. Verify43758666300 passed Python3.11–13,
  all optional engines, VTE startup and all terminal cases except OMP80. Capture
  shows reply with Working before transcript flush: retain assertion but wait
  bounded10seconds for native persistence. Add evalJSON to source docs manifest.
- Installed local RC20 core/connector and restarted confirmed-idle worker; service
  advertises privilege-cases, remains0pending/0completed. No actual root case ran
  on this machine. Final public tag remains pending the CI follow-up.

## RC20 publicly shipped — 2026-11-15

- Published v1.0.0-rc.20 from1d2dc15:
  https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.20
  Verify43758987841 and release43759008899 succeeded. Portable contracts pass on
  Linux/macOS/Windows; disposable POSIX elevation worker/bootstrap and Windows
  UAC parser pass. Genuine Windows consent remains manual coverage. All native
  engine, OMP/OpenCode widths, VTE startup and editor integration gates pass.
- All296 unit regressions pass. Controller report is honestly11/13, two coding
  drift misses/no false interventions. Configured file guards pass independently.
  Security assessment coverage is documented per shipped checks, not universal
  vulnerability/tool certification. Reviewed in review-continuous-supervision.md.
- All published SHA256SUMS verified: wheel246964B, source424523B, VSIX10280B plus
  both separate engine sources. Manifest references20 and matches asset hashes;
  source includes evaluationJSON; VSIX includes diagnostics/no machine bootstrap.
- Installed exact public wheel, refreshed local VS Code connector and restarted
  confirmed-idle worker. RunningRC20 advertises privilege-cases and supervision;
  0pending/0completed/no active attempts. Installed disposable HTTP assessment,
  case dry-run and doctor smoke pass. No root/UAC case or real target/task was
  executed on this user's machine. Existing VS Code windows need reload.
- Source cleanup leaves about30MiB under ppp; optional runtimes/models stay outside.
  RC20 request complete. Further quality work: broader security lab coverage,
  stronger optional controller models and manual Windows UAC/native macOS UI checks.

## Post-RC20 security assessment improvements — 2026-11-16

- Added opt-in exact-URL OPTIONS method advertisement and cookie attribute checks.
  Pure analyzers are separated from network/scope enforcement. Cookie names and
  values are not retained; advertised methods are not executed or called exploits.
- Reject nonfinite scope timing, invalid lifetimes and ambiguous URL characters.
  Security profile now separates hypothesis/probe/review/remediation/retest and
  treats target/tool content as untrusted evidence. This guides behavior rather
  than claiming deterministic model enforcement.
- Adversarial review checked secret retention, unsupported exploit claims, request
  budgets, scope bypass and evidence references. New local fixtures and RC20
  portable tests pass: 21 cases. Diff whitespace check passes.
- Full Windows/Python 3.14 suite: 299 cases, 4 failures, 2 errors, 2 skipped.
  Failures are in untouched relocation, autostart, Bun paths, export mode,
  executable decoding and /tmp screenshot tests; full suite is not green here.
- Source changes only; no release, installation, privileged execution or remote
  assessment. Next: platform-neutral full-suite fixtures and broader attack labs.

## RC21 web and IT security candidate - 2026-11-16

- Versioned Python core 1.0.0rc21 and connector 1.0.21. Added browser/CORS probes,
  cookie prefix checks, bounded explicit local configuration audits and defensive
  report comparison. Usage: rc21-security.md; review: review-1.0.0rc21.md.
- Hardened scope/pin/URL validation and expiry before probes; report header hashes
  replace arbitrary values. Nmap imports are size-bounded before parsing, reject
  NUL encodings/DTD/entities, and enforce every host/address/port combination.
- Retest comparison requires equivalent completed coverage and matching evidence;
  failed response probes cannot masquerade as successful retest coverage.
- Fixed Windows storage relocation using path comparisons/relative reconstruction;
  corrected platform-specific unit-test assumptions without claiming Windows ACL
  or human native elevation coverage. Added RC21 portable CI security fixtures.
- Full Windows/Python 3.14 offline suite: 310 tests, no failures/errors, 3 platform
  skips. Final security contracts rechecked after retest evidence validation.
  Structural files/directories, syntax/import and diff whitespace checks passed.
- Wheel/source build and thin-core checks pass. Candidate artifacts live under
  dist/rc21; build tools are isolated under .runtime/rc21-build. No global install,
  publication, privileged case or remote security assessment was performed.
  An isolated wheel install with declared dependencies passed 32 security tests
  (1 platform skip); source contents and public connector version were verified.
  SHA256SUMS accompanies the wheel, source archive and VSIX.
- Next release gate: cross-platform CI and native release verification. Existing
  upstream engine assets remain pinned to their verified RC20 source archives.
  Known scope/timeouts, local race and observation limits remain documented.

## RC21 publicly shipped - 2026-11-16

- Published v1.0.0-rc.21 from 5551407574761c42f610a7b61acf5540c682c1f9:
  https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.21
- Verify 43865002117, portable 43865002090 and release 43865513858 succeeded.
  Python 3.11/3.12/3.13, Linux/macOS/Windows security contracts, native engines,
  terminals, editor, worker and tool gates all passed. Manual genuine native
  OS-consent coverage remains distinct from automated disposable/parser tests.
- Downloaded all public release artifacts and verified every SHA256SUMS entry:
  wheel 253762 bytes, source 440068 bytes, connector 10281 bytes, and both engine
  source archives. Release notes document features, evidence and coverage limits.
- Installed the exact public wheel only into the isolated build/test environment;
  32 RC20/RC21 security tests passed with one platform skip. No global install,
  running-service changes, privileged execution or remote assessment was performed.
- Requested RC21 publication is complete. Future expansion can address broader
  authenticated web/host coverage and the documented isolation/timeout limitations.

## RC21 documentation and Windows runtime recovery - 2026-11-16

- Expanded README and rc21-security.md with the RC20-to-RC21 comparison, behavior
  and architecture changes, published-version installation, command examples,
  comparison fields and explicit coverage limits. RC20's guide now links forward
  instead of mixing later changes into its baseline. Changelog separates the
  published release from subsequent source fixes.
- Reproduced the Windows NUL-filled @actions/core package manifest despite an old
  ready marker. Setup now validates and hashes hoisted manifests, preserves
  damaged node_modules, repairs from a fresh temporary cache, uses copyfile on
  Windows, checks real startup imports and atomically records readiness only on
  success. Corruption's original cause remains unknown.
- Repaired the affected local runtime without modifying provider/account files:
  803 packages installed, 708 manifests validated, actual codelaboon home screen
  opened in a temporary terminal session and closed successfully. Native startup
  completed its own database migration. Damaged dependencies remain preserved.
- Four new runtime integrity regressions pass. Full local suite: 314 tests,
  zero failures/errors, 3 platform skips. Documentation checks pass for 25 relative
  links/anchors, balanced code fences and CLI option examples. Diff whitespace
  check passes. Review distinguished manifest checks from full content integrity
  and the post-release source fix from immutable RC21 artifacts.
- Original RC21 tag/assets remain unchanged. These source changes require the
  updated checkout/installation; the affected installed launcher uses this checkout.


## RC22 candidate / task conversations
- Added updater/runtime recovery, status diagnostics, live monitors, installed-engine task routing and authenticated browser operations.
- Tasks now open as conversations with durable human guidance, notes and checkpoint inclusion receipts. Immutable elevated cases stay note-only. Existing running workers are not restarted.
- GUI fixture verified note submission; conversation, API and engine contracts added to portable CI. RC22 remains unpublished.


## RC23 / task access and release
- Fixed task navigation with real chat routes, history, visible composer and mobile detail navigation.
- Added shared terminal task conversation viewer, launcher Tasks entry, seven engine aliases and direct bypass.
- Added real-browser navigation/live-output/guidance smoke and Textual interaction tests. Full347 tests pass (3 skipped) before final release validation.
- RC23 publication explicitly requested; release build and CI pending. RC22 candidate is included without publishing a separate RC22 tag.

RC23 local release verification: Chromium regression passed;347 unit tests pass with3 platform skips. Thin wheel290334 bytes, source499258 bytes; VSIX built, both engine archives pass provenance. Release CI/publication pending.


### RC23 published (2026-11-16)
- Public release: https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.23
- Source commit94dac7bc6187e9ffe7511ac65cc1cd86b86805a4. Release43937514148 and verify43937484881 succeeded; release gates include browser chat, portable contracts on Windows/macOS/Linux and all native engine checks.
- Downloaded and verified five artifacts against SHA256SUMS: wheel290155 bytes, source495136 bytes, VSIX10281 bytes, both immutable engine source bundles. Published wheel task-entry tests pass; optional Textual tests covered by the full local347-test run.
- Existing real task was found through the new projection in retry wait; no task controls or messages were applied.
- Updated public release notes with entry commands, checkpoint delivery and old-worker/elevation limitations. RC22 was not separately published.


## RC24 in progress
Implemented independent task worker/planner models, local/cloud planning, additive system prompts, checkpoint revisions and initial queue configuration. Browser, terminal and CLI settings/changes views share one control plane. Added read-only Git diffs and per-attempt observed files. Native wire and local-no-fallback tests pass; final full/browser/package/release verification pending. Real user task settings untouched.

RC24 local verification complete:360 tests pass,3 skipped; isolated built-wheel settings tests11 pass; real Chromium settings/changes/navigation regression passes at1440/768/390. Wheel300672 bytes and source518108 bytes; VSIX rebuilt, engine provenance unchanged and verified. Publication gates pending.


### RC24 published (2026-11-16)
- Public release: https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.24
- Source8c2f9fd88458bc4187e8f23c0f4ffeb27dc4ee0f. Release43952089523, verify43951889132 and portable43951888967 succeeded.
-360 local tests pass,3 skipped; all11 settings tests passed against the published wheel in isolation. Browser regression covers model/prompt persistence, Changes and task navigation at three widths.
- Five artifacts downloaded and SHA256-verified: wheel300344 bytes, source512634 bytes, VSIX10281 bytes and both unchanged engine source bundles.
- First release attempt hit the pre-existing Jcode UI cleanup /proc race (process exited between exists/read); file-tool smoke had passed. Retried gates passed without runtime edits; tag/source remained unchanged.
- Public notes and usage guide explain role separation, CLI examples, safe checkpoints, local server requirements, model-protocol limits and graceful restart for old workers. No real task was modified.


## RC25 development — task operations and account sources (2026-11-16)

- Reviewed publicRC24/9e85e7d and preserved initial line-ending-only changes.
  Prepared1.0.0rc25.dev0 without publishing or replacing the real installed release.
- Added task state filters, timestamped sender/delivery views, tab-persistent drafts,
  Ctrl/Cmd+Enter and last-message recall; historical attempt inspection/logs, atomic
  checkpoint retries and explicit worker scheduling controls across browser/CLI/TUI.
  Retry never duplicates active work, revises elevated cases or clears other jobs'
  cooldowns. Fixed nested portable runner dropping its granted task environment.
- HowToFix key form/hidden terminal prompt and authenticated live model discovery
  added. Public endpoint returned401withoutkey. Copilot GitHub device OAuth,
  private token persistence and chat-capable account models integrated with the
  shared native gateway. Both sources remain outside zero-cost free Auto.
- Windsurf/Devin uses official native auth/models/task CLI, with lazy verified
  installation from static.devin.ai SHA256 manifests. No shell installer or real
  native binary was executed during QA; fixtures cover checksum/host rejection,
  model namespace, permissions and Windows ARM64 selection. No invented SWE raw API.
- 382unit tests pass. Real Chromium checks pass source and isolated-wheel flows:
  draft reload, keyboard send/recall, history/log redaction, retry, worker pause/
  resume, mobile390px layout and API-key privacy. Existing portable/browser CI
  jobs extended; no duplicate browser workflow added. Structural checks and JS
  parsing pass. Reviewed docs/review-1.0.0rc25.md.
- Thin development wheel309548B and source537255B built under/tmp. New account,
  attempt and web modules/assets present; installed wheel tested only in isolated
  /tmp environment. Actual user worker/tasks/settings/accounts were not changed.
  No provider inference or account OAuth authorization performed. Live HowToFix,
  Copilot and Devin verification requires the user's own connection/credentials.
- Usage: docs/task-operations-and-accounts.md. PublicRC24 remains unchanged.

RC25 release preparation: finalized1.0.0rc25 and connector1.0.25, updated README,
CHANGELOG, architecture, release notes and review. Rebuilt the final wheel
(309750B) and source archive below1MiB; rebuilt the10276B VSIX and
staged the unchanged pinned engine bundles. 382 tests pass; 27 provider/task/retry
tests pass against the installed final wheel in
isolation. Structural checks, JS parsing, core packaging and engine provenance
pass; real Chromium task operations pass for source and installed wheel.
Publication gates pending.
