# codelaboon

**A local, terminal-first coding agent for multiple AI providers**

codelaboon is a cross-platform CLI harness for calling AI models through their
provider APIs. It works from source with no installation step, and installs as
a `codelaboon` command on your `PATH`.

## Overview

### What changed in RC28

Open a task in `codelaboon tasks --open` to chat with its orchestrator. Actual
model replies and partial replies appear in the thread alongside the plan and
independent-check status; command diagnostics remain under **Raw attempt output**.
New web tasks default to one verified coding cycle and require an actual project
check rather than assuming a security script exists. Choose 0 cycles explicitly
for continuous work. Send a follow-up after completion to continue the same task. While a cycle is
active, your message joins the next checkpoint. Pauses and provider cooldowns
remain in force. Explicitly stopped or elevated cases keep their existing policy.

Engine task entry points, such as `codelaboon opencode --tasks TASK_ID` and
`codelaboon jcode --tasks TASK_ID`, share this conversation and durable history.
The next attempt receives recent replies and the independent-check failures so
the orchestrator can direct workers to fix them. Restart the background worker
at a safe checkpoint after updating to enable the new conversation feature.

OpenCode/Kilo task launchers now place the instruction before their variadic
attachment option. The previous ordering made the engine treat
`Execute the attached task specification.` as another filename; the SQLite
migration message preceding it was not the cause.

Free-provider exhaustion now returns a retryable 503 with `Retry-After`, and
account-scoped cooldowns survive engine gateway restarts. A Kilo 429 or Freebuff
admission failure means an upstream availability/account issue when the local
gateway has already answered. This changes failover, backoff and diagnostics;
it does not create provider quota or allow paid fallback.

### What changed in RC27

Create background tasks directly in `codelaboon tasks`: choose **New task** or
press **Ctrl+N**, enter the objective, project, scope and verification commands,
then queue. The form lists installed engines and defaults to one verified cycle,
the coding profile, default permissions and no elevation. Errors keep your input;
a successful queue opens the task conversation. The worker starts automatically.
If worker startup fails, the task stays queued and the conversation tells you to
run `codelaboon work start` rather than create a duplicate.

Verification uses JSON argument arrays, for example
`[["python", "-m", "unittest", "discover", "-s", "tests"]]`.
Commands run in the selected project without shell expansion. Use **Settings**
after creation to change models and additive instructions at the next checkpoint.

The new `codelaboon proxy` command runs a stable gateway for desktop apps and
editors on `http://127.0.0.1:8766`. It shares the existing Messages, Responses,
Chat Completions and model-discovery backend. Keep its terminal open while clients
are connected. Its local credential persists across restarts; provider credentials
remain in Codelaboon. Use `--port` or `--token-file` for a separate instance.

For Claude Desktop on Windows:

1. Start `codelaboon proxy --model free` (or choose `PROVIDER/MODEL`).
2. In another terminal, run `codelaboon proxy --show-token` to read the local key.
3. In Claude Desktop, open **Help > Troubleshooting > Enable Developer Mode**.
   After restart, open **Developer > Configure Third-Party Inference**.
4. Choose **Gateway**, base URL `http://127.0.0.1:8766` (without `/v1`),
   **Static API key**, and **Bearer**, then enter the local key.
5. In **Models**, add the explicit model ID `free` (or the same `PROVIDER/MODEL`
   selected above) to the model list and disable model discovery. Desktop's
   auto-discovery shows only recognizable Claude IDs, so a working gateway can
   otherwise leave the picker empty. `codelaboon proxy --desktop-models --model free`
   prints the corresponding `modelDiscoveryEnabled` / `inferenceModels` fields
   without creating credentials or starting a server. Use the exact ID in `name`;
   do not assign Claude capabilities to a non-Claude route with `behavesAs`.
6. Start a local conversation. Built-in Claude model names route to the model
   chosen with `--model`; explicit provider/model IDs retain their own route.

Running `codelaboon proxy` starts the gateway only; it does not launch or configure
Desktop. Keep it running before opening the app. A connection-refused error means
the gateway is stopped or the app is using a different address or port.

This follows Anthropic's [Desktop gateway configuration](https://code.claude.com/docs/en/llm-gateway-connect#desktop-app)
and [third-party inference fields](https://claude.com/docs/third-party/claude-desktop/gateway).
Desktop ignores `ANTHROPIC_BASE_URL` in shell or Claude Code settings. Organization
configuration may make the form read-only. Cloud environments and Remote Control
are unavailable in gateway mode; a loopback URL cannot serve remote SSH hosts.
Non-Claude routes use Codelaboon's compatibility adapter and may not support every
Desktop feature or content type. Token counting is a local estimate and translated
routes do not preserve Anthropic prompt caching. Desktop UI and live inference
validation remain pending; offline protocol tests cover discovery, authentication,
Messages streaming and tool translation.

### Vercel AI Gateway

Run `codelaboon configure vercel` and enter an **AI Gateway API key** from your
Vercel dashboard. You can also use `AI_GATEWAY_API_KEY`, connect **Vercel** in the
TUI key dialog, or choose **Vercel AI Gateway** in the web provider connection form.
A Vercel account token (`VERCEL_TOKEN`) is not an AI Gateway API key.

```powershell
codelaboon models list vercel
codelaboon models list vercel_free
codelaboon chat vercel anthropic/claude-sonnet-4.6 "Explain this repository"
codelaboon proxy --model vercel/anthropic/claude-sonnet-4.6
```

Use an exact model ID returned by the live catalogue; the example model may not
be available for your account. CLI chat takes Vercel's `vendor/model` ID; task,
engine and local proxy selections add the provider prefix: `vercel/vendor/model`.
The default upstream is `https://ai-gateway.vercel.sh/v1`. Both the root URL and
`/v1` are accepted in `providers.toml`; optional `models` are an offline fallback.
Saved API keys take precedence over the environment variable, and key changes
retain the configured endpoint and model fallback list.

The proxy forwards native Messages and Responses requests directly to Vercel;
Messages retain tools, thinking, system blocks and prompt-cache directives.
Chat uses Vercel's OpenAI-compatible endpoint. Gateway credits/model pricing
apply to the unrestricted `vercel` lane. Free Auto uses the separate `vercel_free`
lane, restricted to uniformly zero-priced text models in Vercel's live catalogue.
No configured ID, monthly credit, or expired/offline price record can admit a paid
model; variable-price routes are excluded. The lane reuses your Vercel key only
when both endpoints match, or uses `AI_GATEWAY_API_KEY`. For Claude Desktop, configure the
local gateway and explicit model list as above using `vercel/vendor/model`.
See Vercel's [API setup](https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions)
and [Messages support](https://vercel.com/docs/ai-gateway/sdks-and-apis/anthropic-messages-api).

### What changed in RC25

Task conversations add state filters, timestamps, reload-persistent drafts and
keyboard shortcuts. Inspect the latest 50 attempts and scoped, redacted logs; retry
a finished failure at the next checkpoint; start, pause or resume worker scheduling
from the browser, CLI or terminal. Connect HowToFix with your own API key, GitHub
Copilot through device OAuth, and optional official Windsurf/Devin native accounts
and task execution. Credit and subscription sources stay explicit, outside free Auto.

Use `codelaboon tasks TASK_ID --attempts`, `codelaboon tasks TASK_ID --retry`,
`codelaboon configure howtofix`, `codelaboon login copilot`, or
`codelaboon accounts devin setup`. See
[task operations and account setup](docs/task-operations-and-accounts.md).

### What changed in RC24

Task conversations now include **Models & prompts** and **Changes**. Choose independent
worker and planning models, local or cloud planning, and additive system instructions.
Settings take effect at an attempt checkpoint with revision tracking. Inspect current
Git diffs and filenames observed changing during an attempt in the same task view.

Use `codelaboon tasks TASK_ID --settings`, `--worker-model PROVIDER/MODEL`,
`--orchestrator local --orchestrator-model local/MODEL`, or `--changes`.
See [RC24 task configuration and examples](docs/rc24-task-models-and-changes.md).

### What changed in RC23

Tasks now open as dedicated conversations with live worker output, a visible composer,
checkpoint guidance and delivery receipts. Click a task in the browser to open its
own URL; reload, Back and mobile navigation preserve the task route.

Running `codelaboon` or a bare engine opens a launcher with **Task conversations**.
Use `codelaboon tasks` for terminal task chats, `codelaboon tasks --open` for the browser,
or `codelaboon opencode --tasks TASK_ID` (works with all seven engine aliases).
Use `codelaboon opencode --direct` to skip the launcher. Terminal chats use the
optional `tui` extra; the base install opens task chats in the browser if it is absent.

RC23 also ships the previously unpublished RC22 updater/runtime recovery, diagnostics,
live monitoring and installed-engine task routing. See [RC23 usage](docs/rc23-task-conversations.md)
and the [full changelog](CHANGELOG.md).

### What changed in RC21

RC21 expands the security workflow introduced in RC20:

- **Web assessments:** inspect advertised HTTP methods, cookie attributes and
  prefixes, cross-origin access (CORS), CSP, framing and transport-policy settings.
- **Local IT checks:** audit explicitly named configuration files for private-key
  markers and supported POSIX permission issues without copying their contents.
- **Defensive retesting:** compare equivalent completed assessments to see which
  observations are new, persist, or were not observed again.
- **Stronger boundaries:** validate scope timing, URLs and pinned addresses;
  recheck expiry before probes; hash response-header values; harden nmap imports.
- **Behavior and architecture:** separate response rules, local auditing and
  report comparison; guide the agent through hypotheses, evidence, fixes and retests.
- **Windows reliability:** correct storage relocation path handling.

Start with the [RC20-to-RC21 comparison and examples](docs/rc21-security.md#what-changed-from-rc20),
or read the [full changelog](CHANGELOG.md). The published [RC21 release](https://github.com/zGabrielR1/codelaboon/releases/tag/v1.0.0-rc.21)
contains the wheel, source, VS Code connector and verified engine bundles.
For the Windows NUL-byte dependency/startup failure and its post-release source
fix, see [runtime recovery](docs/native-runtime.md#windows-damaged-runtime-dependencies).

### Harness principles

codelaboon follows PI harness principles:

- **CLI-first means a CLI TUI**: running `codelaboon` opens an interactive
  terminal workspace in the style of Claude Code, OpenCode, Codex CLI and Pi.
  There is no browser dependency for the main flow; `codelaboon web` is an
  optional extra.
- **Your current directory is the project**: start `codelaboon` from a
  repository and that directory becomes the project root for the session.
  It is shown in the header, sidebar and saved conversations.
- **Free by default**: the TUI starts on **`free (Auto)`**, which ranks the
  configured free lanes and picks the best available model automatically.
- **Provider-agnostic**: one command structure for supported providers
- **Declarative, self-documenting**: behavior is described by files in this repo
- **Runtime**: Python 3.11+, provider dependencies, and Bun for the native source
  runtimes; configuration uses the standard-library `tomllib`
- **Cross-platform**: Linux, macOS, and Windows

## `free (Auto)` — the default model

`free (Auto)` is a synthetic provider shown first in the TUI. It does not use a
separate API: it ranks the free lanes you have configured and sends the turn
through the best one, failing over when a provider is rate limited or busy.

- **Availability (55%)** — signed-in/keyless lanes are preferred over lanes
  that would need a login. Today that means `ourfree`, `kilo`, `pollinations`
  and any signed-in account lane.
- **Intelligence (30%)** — stronger free models rank above small ones.
- **Speed (15%)** — faster and lighter models break close ties.

The picker shows the lane `free (Auto)` would use now, for example
`free → gemini/gemini-2.5-pro`. Selecting `free (Auto)` in the model picker
keeps working when a lane goes away: the next ranked candidate is tried at send
time. If no free lane is ready, the TUI says which sign-ins are missing instead
of failing silently.

From the plain CLI the same lane is available as `free`:

```bash
python3 -m codelaboon models list free
python3 -m codelaboon chat free free "Explain this repository"
```

## Free account lane first

The priority lane is genuinely free access. `codelaboon login gemini` signs in
with a normal Google account and onboards Google's free Code Assist tier with no
billing account and no API key; `codelaboon login freebuff` signs in to
Freebuff's ad-funded free tier, also with no subscription and no API key;
`codelaboon login qoder` signs in to a Qoder account, which includes a free
plan; `ourfree`, `kilo` and `pollinations` are keyless free pools. Free tiers
impose their own data policies, and provider terms decide what each tier
includes. Use throwaway prompts on lanes that may log them.

## ChatGPT sign-in and current models

Run `codelaboon login chatgpt`, or click **Continue with ChatGPT** in the web
workspace. Finish authorization in the browser, then refresh the model picker.
This uses OpenAI?s public Sign in with ChatGPT flow with PKCE and verified ID
tokens. Credentials are stored in `chatgpt-session.json` inside your config
directory and refresh automatically. Do not share this file.

The picker requests the selected account?s live catalogue, respects visibility,
and shows its display names. GPT-6 Luna appears when returned for your account;
plan eligibility and usage limits apply. Subscription inference uses Responses
with storage disabled. Interrupted or failed streams are reported as failures.

An explicit configured API key or `OPENAI_API_KEY` takes precedence and uses
API access instead. API discovery also requests the live model list; old
configured GPT-3.5 rosters no longer determine the picker. Discovery does not
guarantee inference quota. API usage has its own billing.

References: [sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
and [models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference).

## Claude and Gemini account sign-in

`codelaboon login claude` (or **Continue with Claude** in the web workspace)
uses Anthropic's public Claude Code OAuth flow with PKCE. Pro, Max, Ultra, Team
and Enterprise claude.ai accounts receive inference through their plan. A free
claude.ai account can complete the same sign-in, but Anthropic does not
currently include Claude Code or API inference with the free plan; when the
account has no allowance the provider reports Anthropic's own plan error. An
explicit `ANTHROPIC_API_KEY` or configured key takes precedence.

`codelaboon login gemini` (or **Continue with Gemini**) signs in with a normal
Google account, then onboards the account to Google's free Code Assist tier. It
needs no billing account and no API key. This is the project's free-as-in-beer
account lane. Google's terms for the free tier apply: prompts may be processed,
logged or retained by the provider according to that tier's data policy. Use it
for throwaway work, not secrets. An explicit `GEMINI_API_KEY` /
`GOOGLE_API_KEY` uses the paid AI Studio API instead.

Account sign-in needs an OAuth client (the app identity, not an account
credential). Create a free **Desktop app** OAuth client in Google Cloud Console,
then run `codelaboon configure gemini` and import the downloaded JSON (or set
`CODELABOON_GEMINI_CLIENT_ID` and `CODELABOON_GEMINI_CLIENT_SECRET`). The client
is stored privately in `gemini-oauth.json`; no OAuth client credentials are
embedded in this repository.

Credentials live in `claude-session.json`, `gemini-session.json`,
`freebuff-session.json` and `qoder-session.json` inside the config directory
with owner-only permissions and refresh automatically. Do not share these
files. Sign-in tokens are only ever sent to the provider's official endpoint;
a custom `base_url` is refused for account sessions.

## Freebuff (ad-funded free tier)

`codelaboon login freebuff` (or **Continue with Freebuff** in the web workspace)
uses the same device-code login the Freebuff CLI uses: the command prints a URL,
you finish sign-in in the browser, and the CLI polls for the account's token.
Freebuff is funded by ads instead of a subscription, so signed-in accounts get
frontier coding models for free. Free sessions are admitted per model for an
hour and are rejected with a clear message when the account is at a limit, a
model is rate limited, or a model was withdrawn from free mode.

The provider speaks the compiled catalog — the picker rows the Freebuff CLI
ships, addressed by plain wire model ids (MiMo, GLM, DeepSeek, GPT Luna, Solar,
Gemini, Muse Spark and more) — so it needs no catalog handles or device
signing. Models that exist only in Freebuff's server-driven catalog are not
listed. Free-tier data policy applies: prompts may be processed, logged or
retained by the provider, and some rows carry an AI-training notice. Use it
for throwaway work, not secrets.

A token from an installed Freebuff CLI (`~/.config/manicode/credentials.json`),
from `CODEBUFF_API_KEY` / `FREEBUFF_API_KEY`, or from an explicit `[freebuff]`
token takes precedence and needs no browser sign-in:

```bash
codelaboon login freebuff
codelaboon models list freebuff
codelaboon chat freebuff mimo/mimo-v2.5 "Hello"
```

## Qoder (free plan)

`codelaboon login qoder` (or **Continue with Qoder** in the web workspace) uses
the same browser device flow the official Qoder CLI uses: the command prints a
URL, you finish sign-in in the browser, and the CLI polls for the account's
device token, which then refreshes automatically. Qoder accounts include a
free plan, so no subscription or API key is needed to sign in.

For browser device sessions, Qoder's inference gateway only accepts requests signed by the
official client, so chat turns run through the installed `qodercli` binary in
its non-interactive print mode (`qoder -p --model auto --tools ""`). Install
it once with `curl -fsSL https://qoder.com/install | bash`, then sign in
with `qoder login` — or skip that and paste a Personal Access Token from
https://qoder.com/account/integrations as the `[qoder]` `api_key` (or set
`QODER_PERSONAL_ACCESS_TOKEN`), which codelaboon forwards to the binary.
Model discovery is live from `qodercli --list-models` when the binary is
present; otherwise the CLI's documented tiers (`auto`, `performance`,
`efficient`, `ultimate`) are the offline fallback. Free-plan data policy
applies: use it for throwaway work, not secrets.

```bash
codelaboon login qoder
codelaboon models list qoder
codelaboon chat qoder auto "Hello"
```

## Local interfaces

Run `codelaboon` (or `python -m codelaboon`) from any directory to open the
terminal workspace. The directory you start it in becomes the project root,
like `opencode`, `codex` or `claude` started in a repository. The header,
sidebar and saved sessions show that project.

Run `codelaboon web` to start the optional web workspace and open your browser
at `http://127.0.0.1:8765`. Use `--port 9000` to choose a port or `--no-open`
to start without opening a browser. Stop the server with Ctrl+C.

The web workspace includes provider/model discovery, multi-turn conversations,
browser-local history, JSON export, code blocks, copy buttons, and light/dark themes.
Provider credentials stay on the Python server. Messages go to the provider you select.
Conversations are saved in this browser?s local storage; exporting creates a portable JSON copy.
The server binds only to loopback and requires a session token for chat requests.

The terminal workspace supports Ctrl+P for providers, Ctrl+O for models,
Ctrl+N/Ctrl+L for a new chat, Ctrl+S for saved sessions, Ctrl+B to toggle the
sidebar and Ctrl+K to replace an account key. The default interface uses OpenCode; Textual is available through the optional
`tui` extra for the legacy interface.

## Quick start

```bash
cd projects/codelaboon
python3 -m codelaboon --help
```

On first run a configuration file is created automatically with restrictive
permissions:

```text
~/.config/codelaboon/providers.toml   (directory 0700, file 0600)
```

Edit that file to add your API keys:

```toml
[chatgpt]
api_key = "sk-..."
models = ["gpt-3.5-turbo"]

[openrouter]
api_key = "sk-or-..."
models = ["openai/gpt-3.5-turbo"]

[ourfree]
api_key = "ofm-..."
base_url = "http://127.0.0.1:18899/v1"
```

A safe template is available in [`config/providers.toml.example`](config/providers.toml.example).
**Never commit real API keys** — the real `config/providers.toml` is gitignored.

Then:

```bash
python3 -m codelaboon providers list
python3 -m codelaboon models list chatgpt
python3 -m codelaboon chat openrouter openai/gpt-3.5-turbo "Hello"
python3 -m codelaboon chat ourfree deepseek-v4.1-flash-free "Hello"
```

## Installation (adds `codelaboon` to PATH)

From the source checkout:

```bash
python3 -m codelaboon install
```

This installs the core package for the current user and
adds pip's user script directory to your `PATH`:

- **Windows** — updates the user `Path` registry value and broadcasts the
  change; open a new terminal afterwards.
- **Linux/macOS** — appends an idempotent `export PATH=…` line to the shell
  profile(s) that already exist (`~/.bashrc`, `~/.zshrc`, `~/.profile`, fish).

Then open a new terminal and run:

```bash
codelaboon --version
codelaboon
```

`codelaboon install --editable` installs the checkout in editable mode, so code
changes are picked up without reinstalling. `--no-path` installs without
touching `PATH`.

To pull the latest source and refresh the installed command in one step, run:

```bash
python3 -m codelaboon update
```

Use `--no-pull` to reinstall only, or `--no-editable` for a regular user
install. If changes don't seem to take effect, updating/reinstalling (and
restarting `codelaboon`) ensures the running command uses the current code.

Scripted installers are available too:

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/zGabrielR1/codelaboon/main/scripts/install.sh | bash

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

Running from the source checkout works without installing at all:
`python3 -m codelaboon`. The TUI is now a normal dependency; the `[tui]` extra
is retained for compatibility.

## Commands

For a persistent task queue with project/harness rotation, see [WATCH.md](WATCH.md).
Run it with `python -m codelaboon.watch examples/watch.json`; local models can
avoid hosted token quotas, while hosted provider limits still apply.
For local orchestration with cloud-only planning and building, see
[CLOUD-WATCH.md](CLOUD-WATCH.md).

Run `python -m codelaboon work` for the background-worker control menu, or use
`work start`, `work status`, `work stop`, `work pause`, `work resume`, `work logs`
and `work add`. New instructions enter a persistent inbox without restarting.

| Command | Description |
|---------|-------------|
| `providers list` | List providers and whether they are configured |
| `models list <provider>` | List models for a provider |
| `chat <provider> <model> <prompt>` | Send a chat completion request (`free free` uses Auto) |
| `decision <provider> <model> <input>` | Ask typed predicate/choice/score questions |
| `login <chatgpt\|claude\|gemini\|freebuff\|qoder>` | Sign in with an account (plan or free tier) |
| `configure <provider>` | Interactively write an API key or start account sign-in |
| `doctor` | Diagnose Python, dependencies, providers and config |
| `install` | Install for the current user and add `codelaboon` to PATH |
| `update` | Pull latest source changes and reinstall codelaboon |
| `tui` | Interactive terminal UI (the default when no command is given) |

common options for `chat`: `--system`, `--temperature`, `--max-tokens`.

Decision models return probabilities for typed questions:

```bash
python3 -m codelaboon decision openrouter my/decision-model \
  "I was charged twice" \
  --predicate 'refund=Is the customer asking for a refund?' \
  --choice 'department=Which team?|billing,technical' \
  --score 'urgency=How urgent?|Low,High' \
  --json
```

See [docs/DECISIONS.md](docs/DECISIONS.md) and
[`examples/questions.json`](examples/questions.json).

```bash
python3 -m codelaboon chat openrouter my-model "Hello" --temperature 0.2 --max-tokens 200
```

## Terminal UI (the main interface)

Running `codelaboon` opens the pinned OpenCode source fork on `free (Auto)`.
It runs OpenCode's own OpenTUI components, tool executor, themes, history,
sessions and context compaction. The Python process keeps provider credentials
and forwards the native wire protocols through a token-protected loopback gateway.

```bash
python3 -m codelaboon install           # small core; engine dependencies fetched on first use
codelaboon                             # native OpenCode UI in the current project
codelaboon opencode                    # same default engine, explicit command
codelaboon omp                         # OMP; dependencies install automatically
codelaboon kilo                        # optional official Kilo CLI and provider gateway
codelaboon claude                      # Claude Code UI on free (Auto); no Claude subscription
codelaboon crush                       # official Crush UI on free (Auto); automatic setup
codelaboon jcode                       # native Rust UI; free backend, persistent project sessions
codelaboon tui --theme codelaboon-kilo   # explicit native Kilo-derived palette
codelaboon tui --profile security       # authorized pentesting workflow
codelaboon tui --local-only             # local inference, with no cloud model fallback
```

First launch fetches the selected engine and its production dependencies, including
checksum-verified Bun 1.4.4 when needed. Node/npm are not required. Use
`codelaboon install --prepare-runtime` to prepare OpenCode during installation.
Provider discovery has a one-second startup budget and uses cached/default models
while refreshing in the background. Skipped optional packages for other platforms
are normal. Once set up, local inference can use Ollama or llama.cpp's OpenAI endpoint.
Run `codelaboon configure local` to change its loopback base URL. Any installed model,
including a locally chosen model with different refusal behavior, appears in the
model picker. Model behavior depends on the selected weights. `--local-only`
restricts inference routing; it does not sandbox tools or block their networking.

Kilo, Claude Code and Crush install only when requested. `codelaboon claude` starts the
unmodified Claude Code client on Codelaboon's `free (Auto)` gateway, with a free-only
model picker and an isolated profile. It prepares local onboarding preferences
and gateway authentication automatically; no Claude account/subscription is needed.
Project trust and native tool permissions remain active. Free providers serve the
inference; provider availability and quotas still apply. The separate
`codelaboon login claude` provider continues to use Anthropic account/API access.

Crush runs its official native UI and tools, with Codelaboon's free catalogue
already configured. `Ctrl+L` opens models; `Ctrl+P` opens commands and themes.
`codelaboon crush run "your prompt"` supports scripted runs. Sessions and preferences
stay in the separate Codelaboon Crush profile. No Go, Node or Bun installation is
needed for this engine. Upstream Crush retains its [FSL-1.1-MIT license](https://github.com/charmbracelet/crush/blob/v0.101.0/LICENSE.md).

Fresh OpenCode/OMP profiles start with a charcoal/yellow theme derived from the official Kilo
CLI theme. Existing native theme choices are preserved. Both engines keep their
own upstream editor, menus, tools and effects.

The native sidebar shows delegated child sessions, background-worker queue/status,
context usage, tasks, changed files, MCP and LSP status. The welcome screen has an
animated whale; task activity uses OMP's activity frames. `CODELABOON_NO_ANIMATION=1`
disables welcome/installer animation; native animation settings control task effects.

OpenCode keys: `Ctrl+P` commands; `Ctrl+X`, then `M` models, `T` themes, `B` sidebar,
`L` sessions, `C` compact. `Up` in an empty composer recalls the last sent prompt;
`Down` moves forward. `/connect` opens native provider setup. Python account login
remains available as `codelaboon login chatgpt|claude|gemini|freebuff|qoder`.
Python-configured ChatGPT, Claude, Gemini and Freebuff models are also exposed to the
native runtimes with their respective wire protocols. Qoder Cloud Agents remains
a separate remote agent/chat interface; it is not advertised as a local tool model.

See [native runtime and worker guide](docs/native-runtime.md) for provenance,
provider limits, background setup, security/local profiles and verification.

## Supported providers

- **ChatGPT / OpenAI** (`chatgpt`) — OpenAI-compatible chat completions or a
  ChatGPT account plan
- **Claude** (`claude`) — Anthropic Messages API or a claude.ai account plan
- **Gemini** (`gemini`) — Google AI Studio API key or a Google account on the
  free Code Assist tier
- **Freebuff** (`freebuff`) — a Freebuff account on the ad-funded free tier
  (device-code login; no subscription, no API key)
- **Qoder** (`qoder`) — a Qoder account on the free plan (browser device
  login; chat runs through the official `qodercli` binary)
- **NVIDIA Nemotron** (`nvidia`) — NVIDIA hosted endpoints
- **OpenRouter** (`openrouter`) — multi-provider aggregator
- **Luna** (`luna`) — Luna AI endpoints
- **Our Free Model** (`ourfree`) — the local forward gateway of the
  [dsh-our-free-model](https://github.com/Ebony-Vinyl/dsh-our-free-model)
  plugin for DeepSeek Harness
- **Kilo** (`kilo`) — Kilo AI's public gateway free pool, completely keyless
- **Pollinations** (`pollinations`) — keyless OpenAI-compatible text API with
  live model discovery and an optional token for higher limits

Each provider implements the shared contract in [`providers/base.py`](providers/base.py).
API keys, base URLs, default models and request payloads are provider-specific;
check the provider module you are using.

### Our Free Model (free lane)

The `ourfree` provider turns the dsh-our-free-model local gateway into an input
for the model catalogue. Its free lanes remain subject to upstream quotas and availability. The
offline fallback list leads with DeepSeek:

| Model | ID |
|-------|----|
| DeepSeek V4.1 Flash | `deepseek-v4.1-flash-free` |
| DeepSeek V4 Flash | `deepseek-v4-flash-free` |
| GLM 5.3 Flash | `glm-5.3-flash-free` |
| MiMo V2.6 Flash | `mimo-v2.6-flash-free` |
| MiMo V2.5 | `mimo-v2.5-free` |
| Nemotron 3 Ultra | `nemotron-3-ultra-free` |
| Nemotron 3.5 Lightning | `nemotron-3.5-lightning-free` |
| Ling 3.0 Flash Fin | `ling-3.0-flash-fin-free` |
| Space Bunny | `space-bunny-free` |
| Union Alpha | `union-alpha` |
| Muse Spark 1.3 | `muse-spark-1.3-contributor-free` |
| Muse Spark 1.2 | `muse-spark-1.2-contributor-free` |
| Jev 1.13 | `jev-1.13-free` |

The catalogue follows the upstream refresh: `models list ourfree` discovers the
live roster from the gateway's `GET /v1/models`, so newly added free models
appear without touching this repo. The list above is the offline fallback used
when the gateway is unreachable.

Setup:

1. In the plugin, enable the forward listener (Settings → Our Free Model →
   Local Forwarding). It binds `127.0.0.1:18899` by default; if that port is
   taken the listener moves and the settings page shows the actual one.
2. Copy the base URL and generate the API key (`ofm-...`).
3. Run `python3 -m codelaboon configure ourfree`, or write both into
   `providers.toml`:

```toml
[ourfree]
api_key = "ofm-..."
base_url = "http://127.0.0.1:18899/v1"
```

### Kilo (keyless free pool)

The `kilo` provider talks directly to [Kilo AI's](https://kilo.ai) public
gateway — the same keyless free pool the dsh-our-free-model plugin exposes as
its Kilo channel. No account, no API key, no fingerprint gate: it works the
moment codelaboon is installed.

- **Discovery is live**: `models list kilo` fetches the gateway's listing and
  keeps only its `isFree` slice — everything else on that gateway is a paid
  id that would answer 401 keyless.
- **Auto-routers** `kilo-auto/free` and `openrouter/free` are the pool's
  stable entry points and the offline fallback roster.
- **Reasoning** — models that declare the parameter accept an effort level
  (`off`, `low`, `medium`, `high`); the provider maps it onto the gateway's
  `reasoning` field when a caller passes one.
- **Privacy**: the gateway's own model cards state that free-pool prompts may
  be logged upstream and used to improve its services. Keep secrets off this
  lane.

No configuration is required; `providers.toml` only needs a `[kilo]` table if
you want to pin models or override the base URL:

```toml
[kilo]
api_key = ""
models = ["kilo-auto/free", "openrouter/free"]
```

Then:

```bash
python3 -m codelaboon models list kilo
python3 -m codelaboon chat kilo kilo-auto/free "Hello"
```

### Pollinations (keyless free text pool)

The `pollinations` provider talks to [Pollinations](https://pollinations.ai)'s
public text API. No account, key or local service is required: the anonymous
tier answers immediately, and an optional token can be set for higher limits.

- **Discovery is live** from `https://text.pollinations.ai/models`; the
  offline fallback is `openai-fast` (GPT-OSS 20B).
- **OpenAI-compatible** requests go to `https://text.pollinations.ai/openai`,
  so chat, TUI and `free (Auto)` all use the same lane.
- **Failover-friendly**: rate limits and timeouts are reported as errors so
  `free (Auto)` can move to the next candidate. One immediate retry covers
  transient stalls on the shared anonymous pool.
- **Privacy**: free-tier prompts may be logged upstream. Keep secrets off this
  lane.

```bash
python3 -m codelaboon models list pollinations
python3 -m codelaboon chat pollinations openai-fast "Hello"
```

To raise limits, put a token in `providers.toml`:

```toml
[pollinations]
api_key = "your-token"
models = ["openai-fast"]
```

## Configuration

Configuration lives at:

```text
~/.config/codelaboon/providers.toml
```

or in `$CODELABOON_CONFIG_DIR/providers.toml` when the environment variable is
set. Keys:

```toml
[provider_name]
api_key = "your-key"
models = ["model-a", "model-b"]

[ourfree]
api_key = "ofm-..."
base_url = "http://127.0.0.1:18899/v1"
models = ["deepseek-v4.1-flash-free"]
```

Permissions are set to owner-only automatically.

## Verification

```bash
scripts/verify.sh        # structural, syntax, import and secret-file checks
scripts/test.sh          # offline unit tests
python3 -m codelaboon doctor
make check               # same core checks (requires make)
make all                 # checks plus optional markdown linting
```

`make` is not required to use the harness.

## Project structure

```text
codelaboon/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── pyproject.toml
├── Makefile
├── codelaboon/            # CLI package
│   ├── __init__.py
│   ├── __main__.py        # `python -m codelaboon`
│   ├── cli.py
│   ├── chatgpt_auth.py    # Sign in with ChatGPT (OAuth + PKCE)
│   ├── decision.py        # Typed decision protocols
│   ├── free_auto.py       # free (Auto) ranking and failover
│   ├── install.py         # `codelaboon install` (pip + PATH)
│   ├── update.py          # `codelaboon update` (pull + reinstall)
│   └── tui.py             # CLI TUI (default interface)
├── providers/             # Provider implementations
│   ├── base.py            # Shared provider contract
│   ├── chatgpt/
│   ├── nvidia/
│   ├── openrouter/
│   ├── luna/
│   ├── ourfree/           # dsh-our-free-model local gateway
│   ├── kilo/              # Kilo AI keyless free pool
│   └── pollinations/      # Pollinations keyless text API
├── examples/
│   └── questions.json     # Decision question example
├── config/
│   ├── providers.py       # Config load/save (user config dir)
│   └── providers.toml.example
├── docs/                  # Harness documentation
├── scripts/verify.sh      # Structural verification
└── CURRENTTASK            # Active objective tracker
```

Reference clones and development runtimes live outside the checkout under
`~/.cache/codelaboon/development`. See [lean storage and swarms](docs/lean-runtime.md).

## Contributing

1. Keep behavior declarative and documented in `docs/`
2. Add new providers as a module implementing `BaseProvider`
3. Run `scripts/verify.sh` before committing
4. Do not commit `config/providers.toml` or any real secret

## Release

Releases are tagged from the default branch, e.g.:

```bash
git tag -a v0.1.0 -m "codelaboon v0.1.0"
```

See [CHANGELOG.md](CHANGELOG.md).

## License

Personal use only — see [LICENSE](LICENSE). codelaboon is a personal
project; no redistribution or commercial use without the owner's
permission, and each provider's own terms continue to apply.


### Native workspace flow

The default workspace uses the native OpenCode keys and commands listed above.
The launch directory is the project. Themes, prompt history and sessions persist
under Codelaboon's native runtime directories. Use the command palette to change
models, connect providers or change the theme.

### RC2: keep your work between sessions

Completed TUI conversations save automatically to `sessions/` in the configured
codelaboon directory. Ctrl+S (or `/sessions`) opens searchable history. Select a
conversation to restore its provider, model and full message context. `/export`
shows its JSON file path. Invalid session files are skipped individually.

The web sidebar supports history search and an archived view. Desktop header
controls rename, archive or restore the selected conversation. Archiving is
reversible. Drafts recover after reload and when switching saved conversations.
Stop waiting restores the draft and controls; the provider may continue executing
and billing the original request. It does not promise upstream cancellation.

### WusRouter and switching accounts

WusRouter (`wusrouter`) discovers its full public catalog live from
https://wusrouter.com/v1/models. Catalog availability does not establish chat
quota or free access. Sign up at https://wusrouter.com/ in your browser and
create an API key, then run `codelaboon configure wusrouter` or set
`WUSROUTER_API_KEY`. In the TUI select WusRouter with Ctrl+P; its connection
dialog opens signup and accepts the key privately. Ctrl+K (or `/key`) lets you
replace the saved key to switch accounts. Ctrl+R refreshes the live models.
The configured `models` list is only a fallback if discovery fails.

### Qoder without installing its CLI

A Personal Access Token can use the official
[Cloud Agents HTTP API](https://docs.qoder.com/cloud-agents/quickstart)
without any local Qoder binary or additional SDK. This route is selected whenever
a PAT is configured, including when a CLI is already on PATH. Set `QODER_PERSONAL_ACCESS_TOKEN` or
`QODER_PAT`, paste the PAT with `codelaboon configure qoder`, or select Qoder
and press Ctrl+K in the TUI. The same model discovery and chat route serves
CLI, TUI and web callers. Browser device sign-in continues to use the CLI lane.

Cloud Agents access and quota are required; this is not a promise of free
personal-plan inference. Create a cloud environment in Qoder first. Each chat
call creates a remote agent with no tools and a new remote session, and sends
the conversation as text. Those resources remain visible in your Qoder account;
cloud model and sandbox usage may consume credits. Errors never silently retry
through the CLI. Live authenticated inference still needs account verification.

The TUI welcome screen now includes a whale and an ASCII Codelaboon wordmark,
with a compact layout for narrow terminals.

### Continuous swarms (RC16)

The background supervisor can repeat verified swarm cycles until you stop it:

```bash
codelaboon swarm "Improve performance while preserving behavior" --continuous \
  --controller local --workers 4 --check 'python3 -m unittest discover -s tests'
codelaboon swarm --status
codelaboon swarm --pause ID
codelaboon swarm --resume ID
codelaboon swarm --stop ID
```

`local` uses the local model to route planning and swarm-building cycles. Choose
`--controller worker` for a native coordinator that directs the swarm without a
local model. `--interval 60` is the default delay between cycles; `--cycles 0`
continues indefinitely. Acceptance checks are mandatory in continuous mode.
`codelaboon work enable` enables the supervisor at login/boot. Pause/stop lets the
active cycle finish, including checks. OpenCode remains the default interface;
`codelaboon jcode` opens the optional native Jcode UI with saved project sessions.
See [continuous swarm operations](docs/lean-runtime.md#continuous-swarms-rc16).


### Verified free models and editor integrations (RC17)

```bash
codelaboon models check free             # real replies and tool-result checks
codelaboon models list free              # verified chat models; native coding pickers require tools
codelaboon ide install                   # connect the official Claude Code VS Code extension
```

Model discovery follows live free catalogs. Stale IDs, failed replies and broken
coding-tool routes stay out of verified pickers. Rate limits defer checks instead
of declaring models retired; background checks respect retry windows. Kilo's full
free catalog and an explicitly zero-priced Z.AI Flash lane expand the candidates.

The lightweight VS Code connector retains the official Claude UI, editor context,
permissions, diffs and sessions while using Codelaboon's backend. It also opens
OpenCode or optional engines in integrated terminals. Provider keys remain in
Codelaboon. Commands support connecting, disconnecting/restoring owned settings,
checking models and opening native engines.

See [model health](docs/free-model-health.md) and [editor setup](docs/editor-integrations.md).

Codex is available as `codelaboon codex`. To connect its official VS Code
extension, run `codelaboon ide install --engine codex`, then use **Codelaboon:
Open Codex**. Its native app-server uses an isolated Codelaboon profile and the
same free backend. **Disconnect Codex** restores the previous CLI setting.

Shared sessions are available with `codelaboon sessions list` and
`codelaboon sessions resume UNIVERSAL_ID --engine codex` (or another engine).
A one-time `sessions convert` also exports native sessions for independent agents
without adding them to the library or requiring Codelaboon at continuation time.
See [universal sessions and standalone conversion](docs/universal-sessions.md).


### RC20: scoped security, permissions and diagnostics

Continuous tasks support explicit full agent permissions, immutable security
scopes, local scope review and file allowlists. Root/admin actions use separately
reviewed, expiring native OS approval cases on Linux/macOS/Windows. Security
assessments include bounded HTTP/TLS/exposure checks and scoped nmap evidence.
Routing learns from observed latency and independent task checks; a VS Code
Diagnostics view exposes operational state. See [RC20 usage, evaluation and
platform coverage](docs/rc20-security-and-operations.md).


### RC25: task operations and account connections

RC25 adds task state filters, attempt history and scoped historical logs,
checkpoint retries, worker scheduling controls, persistent task chat drafts and
keyboard shortcuts. Browser key entry and live HowToFix discovery join GitHub
Copilot device OAuth and the official Windsurf/Devin native account connector.
Credit/subscription sources remain explicit choices outside free Auto.
See [task operations and account setup](docs/task-operations-and-accounts.md).
