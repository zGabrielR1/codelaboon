## 1.0.0rc43

- Show why a task failed in the browser and attempt history using recorded provider, engine, planning and verification evidence.

## 1.0.0rc42

- Compare local security audits to track new, persisting, and no-longer-observed findings.
- Leave findings inconclusive when the retest sample is truncated and require equivalent file and permission coverage.
- Add `security compare --fail-on-new` for baseline-based CI checks.

## 1.0.0rc41

- Detect likely GitHub and Stripe live credentials in explicitly named local files without retaining matched values.
- Add a severity threshold to local audits for CI, and apply it to this project's release configuration.
- Open local audit inputs through no-follow directory handles where supported.

## 1.0.0rc40

- Sort the web task queue by recent attempt activity.
- Reduce idle web polling and skip periodic requests from hidden tabs.
- Scan attempt receipts once per monitor snapshot and skip corrupt receipts.
- Bound conversation event memory and open selected historical logs without scanning other attempts.

## 1.0.0rc39

- Offer Free (Auto) in Web Chat and show which provider and model answered each turn.
- Reuse routing observations across candidates, rank non-streaming latency, and try another provider promptly after rate limiting.
- Synchronize linked desktop agents with continuous-task pause and stop controls.
- Show OpenCode and OMP runtime health and maintenance results alongside the task queue.

## 1.0.0rc38

- Put desktop controls beside continuous tasks and allow eligible jobs to opt in to desktop access each cycle.
- List desktop agents in Tasks and support pause and resume from the task UI and MCP.

## 1.0.0rc37

- Simplify task workspace labels, worker status, and App verification progress.

## 1.0.0rc36

- Add Linux Build → Launch → Verify jobs with a saved accessibility flow, private display, and independent checks against both builds.
- Show app verification live in the task view with pointer takeover and clean relaunch on return.
- Keep regression repairs in detached worktrees across attempts and include patches, check logs, and screenshots in the handoff.
- Add opt-in native desktop control to continuous Jcode swarms and supported engines, plus configured fallback model routes for regression jobs.

## 1.0.0rc35

- Add shared Windows and Linux desktop actions through the web workspace and local stdio MCP.
- Open terminals, run commands, access the task queue and control a visible Chromium session.
- Add opt-in MCP launch configuration for supported native engines and configuration snippets for other clients.

## 1.0.0rc34

- Set up and test Claude.ai browser chat from Connections, with a direct link from the chat provider picker.
- Show a copyable Firefox add-on manifest path and distinguish a saved setup from a verified connection.
- Preserve provider display names after saving an API key and improve model and Firefox error messages.

## 1.0.0rc33

- Add a Claude.ai browser provider that uses the default model of a signed-in Firefox session through a temporary add-on and an authenticated loopback bridge.
- Expose it as `claude_browser` in the CLI, the web workspace and native engine model pickers; the gateway route is `claude_browser/web-default` and remains text-only.
- Include the add-on assets in the wheel and show provider display names in the web provider list.
- Keep the workspace header within phone widths without horizontal scrolling.

## 1.0.0rc32

- Opening a web task in Oh My Pi on Windows now uses OMP-compatible session paths. Drive colons and path separators are encoded before writing the imported conversation.

## 1.0.0rc31

- Redesigned Chat, Tasks, and Connections with ivory typography, chartreuse accents, and a pointer-reactive welcome screen that respects reduced motion.
- Added Mistral Labs to Connections and Free Auto. An API-enabled Mistral account is required. Discovery is limited to the documented Labs namespace.
- Expanded OpenRouter Free discovery to live text models with zero pricing, including eligible models without the free suffix. Requests retain the zero-price cap.
- Prioritized newly discovered models, rechecked existing models by expiry, and distinguished temporary failures during tool verification from unsupported tool use.

## 1.0.0rc30

- Deduplicate engine launch retries, guard dialogs during in-flight actions, and
  refresh connection state when returning to the browser tab.

- Add task deletion with confirmation, durable scheduler exclusion and retained
  project files and local attempt logs; expose deletion in chat, operations and CLI.
- Open a task in an installed native engine from the web UI using a desktop
  terminal and the existing shared conversation/session route.
- Add a Connections page with browser account sign-in, device-code progress and
  API-key setup. Running engine gateways and the proxy reload saved connections.
- Keep task titles visible on phones, reduce irrelevant controls, preserve
  unchanged chat DOM during polling, and separate activity from assistant replies.
- Show actual failed-check commands, exit codes and bounded redacted output;
  reserve verification time and pause missing verifiers or repeated identical
  failures. Do not penalize model quality for broken verification infrastructure.

## 1.0.0rc29

- Open task conversations in the normal web chat sidebar and composer, with
  shared durable history and automatic updates between worker cycles.
- Import task history into native OpenCode, OMP, Kilo, Jcode, Codex, Claude Code
  and Crush sessions with `codelaboon ENGINE --tasks TASK_ID`. Route human turns
  through the shared orchestrator rather than starting an unrelated chat.
- Stream planning and worker replies in the same native task turn. Preserve
  task pauses, explicit stops, execution scope and independent verification.
- Detect upstream errors inside successful HTTP/SSE responses before forwarding
  a free-provider reply, and cool down Vercel accounts requiring billing setup
  before trying another eligible free provider.

## 1.0.0rc28

- Fix OpenCode/Kilo task launch arguments: variadic `--file` no longer consumes
  the task instruction as a second filename.
- Make task threads durable conversations with real model replies, live partial
  replies, planning/status turns, separate raw logs and follow-up execution after
  completion. Shared engine task views use the same conversation API.
- Include independent-check failures in the next orchestration attempt, rather
  than passing only the previous worker's success claim.
- Default new web tasks to one verified coding cycle and require an existing
  project verification command instead of preselecting a nonexistent script.
- Return retryable 503/Retry-After for exhausted free routes, respect upstream
  retry delays, persist account-scoped provider cooldowns across gateway restarts,
  and distinguish provider capacity from a broken local endpoint.

## 1.0.0rc27

- Add a separate Vercel free Auto lane sourced from live zero pricing. Exclude
  paid, unknown, non-text and variable-price routes; revalidate before requests
  and reject configured fallback IDs when current pricing cannot be established.
  Reuse the Vercel key only on the same endpoint and scope health to its account.

- Add Vercel AI Gateway API-key setup in CLI, terminal and web workspace, using
  `AI_GATEWAY_API_KEY`, live model discovery and an explicit credit lane outside
  free Auto. Preserve configured endpoint/model fallbacks during key rotation.
- Route Vercel Chat, native Messages and Responses through the proxy; retain
  native Messages tool, thinking and cache-control fields.
- Fix query-bearing model discovery and Anthropic pagination metadata; document
  explicit Desktop model lists and seed proxy catalogues without blocking on all
  upstream providers.

## 1.0.0rc26

- Create tasks inside the terminal workspace using New task / Ctrl+N, with an
  installed-engine picker, scope, project, model, independent checks and cycle limit.
  Preserve form input on errors and open the queued conversation after submission.
- Add `codelaboon proxy` for desktop apps and editors, with stable loopback port,
  persistent local credential and explicit Claude built-in model routing.
- Document Claude Desktop for Windows third-party inference setup using the
  official Gateway form; retain existing VS Code launchers and shared wire adapters.
- Add offline terminal and HTTP regression coverage. Claude Desktop UI/live
  inference verification remains pending because the Windows automation helper
  is unavailable in this session.

## 1.0.0rc25

- Improve task conversations with reload-persistent drafts, timestamps, keyboard
  sending/recall and state filters; inspect historical attempt output and results.
- Add checkpoint retry for failed continuous tasks, worker scheduling controls,
  authenticated APIs and shared CLI/terminal controls; preserve explicit worker
  policy across nested portable engine execution.
- Add HowToFix API-key entry/live discovery, Copilot device OAuth/account models,
  and a lazy checksum-verified official Windsurf/Devin native account/task connector.
  Credit/subscription sources are not silently treated as zero-cost Auto routes.
- Add browser/provider/retry/installer regression coverage and browser CI gates.
- See [RC25 task operations and account sources](docs/task-operations-and-accounts.md).

## 1.0.0rc24

- Add revisioned per-task worker models, independent cloud/local planning models and additive system instructions across the shared worker gateway.
- Add browser and terminal settings, CLI updates and atomic initial queue settings; edits apply at checkpoints without mutating active or approved elevated attempts.
- Add read-only Git changes, bounded diffs and observed per-attempt filenames with explicit pre-existing/concurrent-edit labels.
- Add planner failure/budget checks, local-no-cloud-fallback tests, gateway model/prompt tests, API concurrency/auth tests and real-browser settings/changes regression.
- See [RC24 usage](docs/rc24-task-models-and-changes.md).

## 1.0.0rc23

- Fix task clicks to open a dedicated chat route with live output, a visible composer, browser history and mobile navigation.
- Add engine-independent terminal task chats and a visible Tasks option in bare engine launchers. All seven engine aliases accept `--tasks`; `--direct` bypasses the launcher.
- Add a real Chromium task-chat regression to release CI and terminal interaction tests.
- Include the unpublished RC22 recovery, monitoring and task-orchestration work below.


- RC22 candidate: tasks open as conversations with execution updates, captured worker output, durable operator guidance and notes. Guidance is included at the next attempt checkpoint with explicit receipts; active cycles continue. Older workers and elevated approval cases accept notes only.
- Add authenticated browser task queue, installed-engine selection, controls and live monitoring. Add updater runtime-integrity maintenance, force repair, update receipts, terminal resume shortcuts and recovery diagnostics.
- See [RC22 usage and limitations](docs/rc22-updater-and-terminal.md).


- Detect damaged cached source-runtime dependency manifests instead of trusting
  a ready marker alone. Preserve corrupted dependencies, reinstall from a fresh
  cache, and use copyfile installs on Windows. Verify actual startup imports
  before writing an atomic readiness record. See
  [Windows runtime recovery](docs/native-runtime.md#windows-damaged-runtime-dependencies).
- Expand RC21 documentation with a before/after comparison, behavior and
  architecture explanation, installation steps, examples and report interpretation.

## 1.0.0rc21 - 2026-11-16

Published as [v1.0.0-rc.21](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.21).
See the [RC20-to-RC21 comparison and examples](docs/rc21-security.md#what-changed-from-rc20).

- Expand explicit-scope web assessments with OPTIONS method advertisements,
  cookie attributes, synthetic-origin CORS probes and browser policy analysis.
  Separate observations from demonstrated exploitability and preserve budgets.
- Add bounded, read-only audits of explicitly named local configuration files
  for private-key material and POSIX access permissions; never retain contents.
- Compare equivalent completed assessments for defensive retesting; label absent
  findings as not observed rather than claiming a verified fix.
- Tighten URL/pinned-address/timing validation, recheck scope expiry between
  probes, hash response-header values, and harden bounded nmap XML imports.
- Separate pure checks, local audit and report comparison from network execution;
  strengthen evidence-first security behavior and untrusted-output guidance.
- Fix Windows storage relocation path handling and platform-sensitive test
  assumptions; add RC21 web/IT fixtures to portable CI.

## 1.0.0rc20 - 2026-11-15

- Add per-task native full permissions, active local scope review, redirect/replan,
  file allowlists and durable pause/resume; preserve the original objective.
- Add separate expiring root/admin cases with exact command review, native sudo/UAC,
  single-use receipts and bounded elevated worker cycles; never auto-elevate services.
- Add scoped HTTP/TLS/exposure assessments, evidence/remediation reports, tool
  capability detection and exact-host/port nmap cases/import, with real local labs.
- Learn task-aware routing from private bounded latency/outcome observations;
  expose fast/balanced/deep presets without claiming guaranteed model intelligence.
- Add reproducible local-controller evaluation and offline CLI/VS Code diagnostics.
  Small-model regression score is 11/13; document misses and independent file guards.
- Apply native Jcode security overlays in interactive sessions while preserving
  native base instructions and user preferences. Add Linux/macOS/Windows contracts.

## 1.0.0rc17 - 2026-11-15

- Verify free models with real replies, valid function calls and unpredictable
  tool-result receipts. Store private scoped health and filter verified pickers.
- Follow authoritative live/empty catalogs; capability hints cannot resurrect
  retired IDs. Quarantine failures per model and prioritize proven coding routes.
- Add incremental background verification, Retry-After/backoff, streaming reports
  and a daily public free-provider health workflow. Defer rate-limited/account
  lanes without pretending they passed or permanently removing them.
- Expand dynamic Kilo free discovery, official OpenRouter-key reuse and zero-price
  constraints; add the documented Z.AI Flash lane with live free-pricing guards.
- Add a tiny VS Code connector using the official Claude process-wrapper hook.
  Retain native editor/SDK/tool features on the Codelaboon backend, preserve
  unrelated settings/secrets, and restore owned preferences on disconnect.
- Add native engine integrated-terminal commands and a portable VSIX asset.
  Verify SDK/file tools and actual official VS Code chat submission/reply.

## 1.0.0rc16 - 2026-11-14

- Add continuous durable swarms with local-model routing or native worker
  coordination, verified cycle counts, interval/backoff, optional cycle limits,
  and per-objective pause/resume/stop/status controls.
- Reuse the 24/7 supervisor and independent acceptance checks. Persist due times
  and progress across restarts; share each build's budget with its checks.
  Worker-controlled swarms do not load the local router model.
- Make the Jcode UI a complete optional engine: durable project profiles, native
  session resume, display preferences, owned-server cleanup and no headless UI
  timeout. OpenCode remains the default.
- Run queued acceptance commands consistently and preserve literal command
  arguments. Prevent offline local jobs from starving native coordinator jobs;
  reject continuous queues on an outdated running supervisor before writing them.
- Add native Jcode UI/resume/cleanup and two-cycle swarm restart CI checks.

## 1.0.0rc15 - 2026-11-14

- Keep OpenCode as the default UI; ship a small core with pinned engine metadata.
  Fetch verified OpenCode/OMP assets and engine dependencies on first use, or
  prepare OpenCode at install time with `--prepare-runtime`.
- Move development sources/clones/builds outside project backups. Add preview-first
  `storage audit` and non-destructive `storage compact --apply`, with tracked-file,
  destination and live-process guards plus move journals.
- Add optional verified Jcode v0.99.1 Rust execution and bounded native swarms over
  one Codelaboon gateway. Default background builders use Jcode. Keep acceptance
  checks independent, budgeted and logged.
- Unload the service-owned local router model while idle and reload for queued
  tasks. Preserve external router processes, accounts, queues and legacy history.
- Verify real OpenCode VTE rendering/history, native Rust file tools and a native
  two-worker swarm. Publish engine bundles separately; enforce a 1 MiB core limit.

## 1.0.0rc14 - 2026-11-14

- Add `codelaboon crush`: official Crush v0.101.0 native UI, automatically
  downloaded with SHA-256 verification and configured on Codelaboon free (Auto).
- Keep Crush project sessions, global preferences and caches in a separate
  profile. Expose the free model list, native tools/themes and local/security modes.
- Use a private, short-lived native server for `crush run` so fast completions
  reach stdout reliably; interactive mode stays in-process without a daemon.
- Add Crush UI, prompt recall, saved themes, repeated file-tool loops and actual
  VTE checks, plus installer/isolation/server-lifecycle regression coverage.

## 1.0.0rc13 - 2026-11-14

- Start Claude Code on Codelaboon free (Auto), without Anthropic login or a Claude
  subscription. Prepare an isolated profile and free-only native model picker.
- Bridge Anthropic Messages to free OpenAI-compatible providers, preserving text,
  images, tool schemas/calls/results, streaming, usage and provider failures.
- Retain project trust and native tool permissions. Keep provider credentials in
  the loopback backend; do not reuse personal Claude credentials for this engine.
- Add native Claude UI/model-picker and real file-tool checks without an Anthropic
  account, plus adapter and account-isolation regression tests.

## 1.0.0rc12 - 2026-11-14

- Fix OpenCode's blank screen in Fedora Ptyxis/GNOME Terminal. Fast terminal
  background replies could let the frontend send RPC requests before its backend
  worker registered its listener. Add an explicit worker-readiness handshake and
  a bounded startup wait; remove the dependency on terminal response timing.
- Add an immediate-terminal-response regression that reproduced the RC11 failure.
  Verify the fix against the real Fedora VTE terminal library as well as tmux.

## 1.0.0rc11 - 2026-11-14

- Fix default OpenCode startup: bound provider discovery, cache model metadata,
  avoid launch-time model downloads and duplicate empty plugin installations.
- Use the same packaged runtime cache for setup and installed commands; repair
  incomplete setup automatically. Keep OpenCode as the default without a picker.
- Install production dependencies with shared Bun storage. Download verified Bun
  automatically without requiring Node/npm. Keep Textual in the optional extra.
- Add optional official Kilo and Claude Code native CLIs with verified downloads.
  Kilo uses the provider gateway; Claude Code retains upstream account sign-in.
- Cover normal OpenCode startup in CI, including slow/offline catalogue tests.

## 1.0.0rc10 - 2026-11-13

- Keep OpenCode and OMP as the actual native UI codebases. Add Kilo Code's native
  charcoal/yellow palette and an OMP palette adaptation, with upstream MIT notice
  and revision/hash provenance. Saved native theme choices remain respected;
  `tui --theme NAME` selects an explicit native theme.
- Keep OMP logs, sessions, settings and themes inside the Codelaboon profile,
  including isolated background-worker profiles. Use the native condensed
  changelog and avoid checking for an unrelated OMP binary update by default.
- Add repeatable terminal integration checks at 80/160 columns for both engines:
  welcome, model response, prompt recall, themes and settings; wide OpenCode
  also checks delegated/background sidebar sections. Check OMP session/log paths.
- Gate GitHub publication on both native UIs, their upstream type checks, real
  file-tool round trips, Python tests and source-bundle integrity. Preserve
  terminal evidence as CI artifacts and require the tag/package versions to match.
- Add replay-checked source patch export and packaged source hash verification.

## 1.0.0rc9 - 2026-11-13

- Execute pinned OpenCode and Oh My Pi source runtimes with preserved upstream
  themes, tools, sessions, prompt recall, animations and context compaction.
  Add animated Codelaboon branding and delegated/background work to the native sidebar.
- Package provenance-listed runtime sources and reproducible patches; verify OMP's
  native addon integrity and extract installed sources atomically.
- Preserve chat, Responses, Anthropic and Gemini tool protocols through an
  authenticated loopback gateway. Add Freebuff admission, free-route cooldowns,
  explicit OpenRouter free selection, Groq/Cerebras catalogues and local models.
- Add local-only inference and an authorized security profile. Exclude Gemini API
  keys and Qoder Cloud PATs from automatic free selection. Prefer Qoder HTTP
  whenever a PAT is configured. Add official standalone Our Free Model controls.
- Add user systemd/Scheduled Task/LaunchAgent registration, persistent empty queues,
  worker availability probes and routing health metadata. Native background builders
  use the packaged source runtime without a separately installed OpenCode executable.
- Prepare Bun/runtime dependencies during install/update, respect virtualenvs and
  externally managed Python, fix Fish/bootstrap installers, and stop on failed pulls.

- Make the CLI TUI the default interface: running `codelaboon` with no
  command opens a terminal workspace modelled on Claude Code, OpenCode, Codex
  CLI and Pi. The launch directory is the project root and is shown in the
  header, sidebar, `/project` and saved sessions.
- Add `free (Auto)`, the default TUI model and a synthetic CLI provider. It
  ranks configured free lanes by availability (55%), intelligence (30%) and
  speed (15%), displays the lane it will use, and fails over at send time.
  `chat free free` and `models list free` use the same ranking.
- Fix picker and composer keyboard navigation: Up/Down and PageUp/PageDown move
  the picker highlight and Enter selects; Up/Down in the composer recalls
  previously sent prompts. No mouse is required.
- Rewrite ChatGPT sign-in: persist the issued client id before exchange, send
  the documented request headers, tolerate a missing scope claim, and show the
  provider's real OAuth error instead of a generic failure.
- Add `codelaboon install` and scripted installers. The command installs the
  package for the current user and idempotently adds pip's user script
  directory to PATH on Windows and POSIX. `--editable` and `--no-path` are
  supported.
- Add the keyless `pollinations` provider: live model discovery from
  `text.pollinations.ai/models`, OpenAI-compatible chat, optional bearer
  token, transient-timeout retry, and membership in `free (Auto)`. Verified
  live end-to-end, including `chat free free`.
- Fix config-directory resolution so `CODELABOON_CONFIG_DIR` is honored
  without evaluating `Path.home()` first; this also makes auth tests work in
  environments with no home variable.
- Add ranked/failover and new TUI interaction tests; focused suites pass.

## 1.0.0rc8 - 2026-11-08

- Add WusRouter with public live model discovery, API-key chat, and browser
  signup from the TUI. Ctrl+K or `/key` replaces WusRouter/Qoder credentials.
- Add native Qoder Cloud Agents HTTP transport for PAT users without a local
  CLI. Requires Cloud Agents access, quota and an existing cloud environment;
  live authenticated inference remains unverified.
- Add a responsive whale ASCII welcome screen and Codelaboon wordmark.
- Write provider configuration atomically with private temporary files, fsync,
  replacement and a process-local lock to preserve concurrent account updates.
- Clear stale busy/model state when changing TUI credentials; invalidate older
  chat results before the new account's discovery finishes.
- Validate Qoder catalogs and stream frames, bound event size, decode UTF-8
  explicitly, and wait through documented recoverable server retries.
- Repair Makefile verification's stale path and package workflow files so a
  source archive can run the same structural checks as the checkout. Empty
  archive directories are no longer treated as required release content.

## 1.0.0rc7 - 2026-11-05

- Qoder limitation alert, shown on all three surfaces: the CLI prints it
  for Qoder `login`/`configure`/`models list`/`chat`, the TUI logs and
  notifies it when Qoder is selected, and the web workspace shows a
  banner while Qoder is the selected provider. It states that login
  works natively but chat runs through the official `qodercli` binary,
  because Qoder's gateway only accepts signed official-client requests.
  No Qoder provider logic changed.
- License changed from MIT to Personal Use Only: codelaboon is a
  personal project for the owner's own use, with no redistribution or
  commercial use without permission. Each provider's own terms continue
  to apply.

## 1.0.0rc6 - 2026-11-05

- Fixed the TUI model picker: `ctrl+m` could never open it, because in
  terminals Ctrl+M is carriage return — byte-identical to Enter — so it
  was always consumed as a message submit. The picker now lives on
  `ctrl+o`, and it is unified across providers: one list spans every
  connected provider, picking a model from another provider switches the
  provider too, and unconnected account providers show a Connect row.
- Added `qoder`: a Qoder account on the free plan, signed in with the
  same browser device flow the official Qoder CLI uses (PKCE, token
  polled from the OpenAPI host, automatic refresh). Because Qoder's
  inference gateway only accepts requests signed by the official client,
  chat turns run through the installed `qodercli` binary in tool-free
  print mode; a Personal Access Token from
  https://qoder.com/account/integrations is forwarded to it via
  `QODER_PERSONAL_ACCESS_TOKEN`. Model discovery is live from
  `qodercli --list-models` when present, with the documented tiers as
  the offline fallback. Free-plan data policy applies.
- `codelaboon login` accepts `chatgpt`, `claude`, `gemini`, `freebuff`
  and `qoder`; `configure` offers account sign-in for Qoder when no key
  is entered. TUI login dialog and web action menu cover all five
  account providers.
- Session files (`qoder-session.json`, `qoder-machine.json`) are atomic,
  owner-only and refresh automatically.
- Offline tests pass; live Qoder authorization and inference remain
  unverified without a real account and the `qodercli` binary.

## 1.0.0rc5 - 2026-11-05

- Added `freebuff`: a Freebuff account on the ad-funded free tier, signed in
  with the same device-code login the Freebuff CLI uses (browser sign-in, token
  polled from the web app). No subscription, no credits, no API key. Free
  sessions are admitted per model for an hour; limits, waiting-room and
  withdrawn-model rejections are surfaced in plain language. The provider
  speaks the compiled catalog by plain wire model ids, so no catalog handles
  or device signing are needed; models that exist only in the server-driven
  catalog are not listed. Free-tier data policy applies; use it for throwaway
  work.
- `codelaboon login` accepts `chatgpt`, `claude`, `gemini` and `freebuff`;
  `configure` offers account sign-in for Freebuff when no key is entered. TUI
  login dialog and web action menu cover all four account providers.
- A token from an installed Freebuff CLI (`~/.config/manicode/credentials.json`),
  from `CODEBUFF_API_KEY` / `FREEBUFF_API_KEY`, or from an explicit
  `[freebuff]` token is honored without a new browser sign-in. Account tokens
  are refused for custom `base_url` endpoints.
- 100 offline tests pass; live account authorization and inference remain
  unverified without real accounts.

## 1.0.0rc4 - 2026-11-05

- Added `claude`: Anthropic Messages API with an API key, or a claude.ai account
  signed in through the public Claude Code OAuth PKCE flow. Pro/Max/Ultra/Team/
  Enterprise plan entitlement carries over; free accounts can connect but
  Anthropic does not currently grant inference on the free plan.
- Added `gemini`: Google AI Studio API key, or a Google account signed in with a
  user-supplied Desktop OAuth client. The account lane onboards to the free Code
  Assist tier automatically, with no billing account or API key. The OAuth
  client is stored privately, not embedded in the repository. Free-tier data
  policy applies; use it for throwaway work.
- `codelaboon login` accepts `chatgpt`, `claude` and `gemini`; `configure` offers
  account sign-in for Claude and Gemini when no key is entered.
- TUI login dialog and web action menu cover all three account providers.
- Session files (`claude-session.json`, `gemini-session.json`) are atomic,
  owner-only and refresh automatically. Account tokens are refused for custom
  `base_url` endpoints.
- Added a tag-triggered release workflow: tests, builds the wheel/source
  archive, writes SHA256SUMS and publishes a prerelease with downloadable
  artifacts.
- 86 offline tests pass; live account authorization and inference remain
  unverified without real accounts.

## 1.0.0rc3 ? 2026-11-05

- Latest build includes the taste framework visual rework: navigation rail, conversation library, starter rows, mobile action menu, and matching TUI palette.
- Verified 60 offline tests and browser layouts at 390/768/1440px; taste source lint clean.
- Live provider authorization remains unverified.

## 1.0.0rc2 ? 2026-11-05

- TUI conversations save automatically after completed replies. Ctrl+S opens searchable saved sessions; /export exposes the session JSON path.
- Web conversations support search, rename, archive and restore. Drafts recover after reload and when switching saved sessions.
- Stop waiting restores the draft and controls without accepting a late reply. Provider execution may continue.
- Discovery sequence guards reject stale model catalogues, refresh clears invalid model selections, and busy TUI submissions preserve their prompt.
- Atomic session files isolate malformed records and reject path traversal identifiers.

## 1.0.0rc1 ? 2026-11-05

- Default terminal workspace with searchable provider/model dialogs, right session sidebar, slash commands and integrated ChatGPT sign-in.
- Loopback web workspace with local conversation persistence, model discovery, export, code blocks, responsive layout and theme selection.
- ChatGPT public OSS authorization with PKCE, verified identity tokens, token refresh, live account catalogue and Responses inference.
- Stale chat-result guards, error recovery, request timeouts and localhost origin/token checks.
- Original vector whale/code logo; web assets included in wheel and source distribution.
- Verified offline suite and browser fixture flows. Live ChatGPT authorization, subscription inference and cross-platform CI execution remain unverified.

# Changelog

## 1.0.0rc19

- Share persistent conversations across seven native engines using one library ID.
- Add VS Code Sessions sidebar with Import, Export, Convert and Resume actions.
- Convert independent native sessions without library registration or requiring
  Codelaboon when the destination agent resumes. Preserve original source records.
- Fix native import/export command dispatch and Jcode headless resume profiles.
- Include the explicit `codelaboon opencode` default-engine command.


## 1.0.0rc18

- Add native Codex CLI and official VS Code app-server integration with an isolated
  profile, automatic native setup, free backend and restorable editor connection.
- Bridge Responses requests, native function/custom tools and tool results to
  verified free chat providers. Keep OpenCode the default interactive engine.


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
