# codelaboon

**A local workspace for accessing AI models from multiple providers**

codelaboon is a cross-platform, CLI-first harness for calling AI models through
their provider APIs. It works from source with no installation step, and can
optionally be installed as a `codelaboon` command.

## Overview

codelaboon follows PI harness principles:

- **CLI-first**: no web UI; an optional interactive TUI is available
- **Provider-agnostic**: one command structure for supported providers
- **Declarative, self-documenting**: behavior is described by files in this repo
- **Minimal dependencies**: Python 3.11+ and `requests`; configuration uses the
  standard-library `tomllib`
- **Cross-platform**: Linux, macOS, and Windows

## Free account lane first

The priority lane is genuinely free access. `codelaboon login gemini` signs in
with a normal Google account and onboards Google's free Code Assist tier with no
billing account and no API key; `ourfree` and `kilo` are keyless free pools.
Free tiers impose their own data policies, and provider terms decide what each
tier includes. Use throwaway prompts on lanes that may log them.

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

Credentials live in `claude-session.json` and `gemini-session.json` inside the
config directory with owner-only permissions and refresh automatically. Do not
share these files. Sign-in tokens are only ever sent to the provider's official
endpoint; a custom `base_url` is refused for account sessions.

## Local interfaces

Run `codelaboon` (or `python -m codelaboon`) to open the terminal workspace.
Run `codelaboon web` to start the web workspace and open your browser at
`http://127.0.0.1:8765`. Use `--port 9000` to choose a port or `--no-open`
to start without opening a browser. Stop the server with Ctrl+C.

The web workspace includes provider/model discovery, multi-turn conversations,
browser-local history, JSON export, code blocks, copy buttons, and light/dark themes.
Provider credentials stay on the Python server. Messages go to the provider you select.
Conversations are saved in this browser?s local storage; exporting creates a portable JSON copy.
The server binds only to loopback and requires a session token for chat requests.

The terminal workspace supports Ctrl+B to toggle the sidebar and Ctrl+L for a new chat.
Textual is installed with the application so the default command works after installation.

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

## Installation (optional)

```bash
python3 -m pip install --user .
codelaboon providers list
```

This installs a `codelaboon` console script and the Python packages used by the
harness. Running from the source checkout works without installing. The
terminal UI is an optional extra: `python3 -m pip install --user '.[tui]'`.

## Commands

| Command | Description |
|---------|-------------|
| `providers list` | List providers and whether they are configured |
| `models list <provider>` | List models for a provider |
| `chat <provider> <model> <prompt>` | Send a chat completion request |
| `decision <provider> <model> <input>` | Ask typed predicate/choice/score questions |
| `login <chatgpt\|claude\|gemini>` | Sign in with an account (plan or free tier) |
| `configure <provider>` | Interactively write an API key or start account sign-in |
| `doctor` | Diagnose Python, dependencies, providers and config |
| `tui` | Interactive terminal UI (needs the optional `textual` extra) |

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

## Terminal UI (optional)

`codelaboon tui` opens an interactive terminal interface built on
[Textual](https://github.com/Textualize/textual). It is an optional extra to
keep the core harness dependency-light:

```bash
python3 -m pip install 'codelaboon[tui]'
python3 -m codelaboon tui
```

The TUI offers:

- **Provider browser** — all configured providers with their configured status
- **Model catalogue** — the selected provider's models, refreshed live
  (the `ourfree` catalogue is discovered from the gateway on every pick)
- **Multi-turn chat** — type in the prompt box, `Enter` to send; the
  conversation context is kept until you switch provider or model
- **Diagnostics** — `ctrl+d` runs the same checks as `codelaboon doctor`
  inline

Keys: `ctrl+p` providers · `ctrl+m` models · `ctrl+r` refresh models ·
`ctrl+d` doctor · `ctrl+q` quit.

## Supported providers

- **ChatGPT / OpenAI** (`chatgpt`) — OpenAI-compatible chat completions or a
  ChatGPT account plan
- **Claude** (`claude`) — Anthropic Messages API or a claude.ai account plan
- **Gemini** (`gemini`) — Google AI Studio API key or a Google account on the
  free Code Assist tier
- **NVIDIA Nemotron** (`nvidia`) — NVIDIA hosted endpoints
- **OpenRouter** (`openrouter`) — multi-provider aggregator
- **Luna** (`luna`) — Luna AI endpoints
- **Our Free Model** (`ourfree`) — the local forward gateway of the
  [dsh-our-free-model](https://github.com/Ebony-Vinyl/dsh-our-free-model)
  plugin for DeepSeek Harness
- **Kilo** (`kilo`) — Kilo AI's public gateway free pool, completely keyless

Each provider implements the shared contract in [`providers/base.py`](providers/base.py).
API keys, base URLs, default models and request payloads are provider-specific;
check the provider module you are using.

### Our Free Model (free lane)

The `ourfree` provider turns the dsh-our-free-model local gateway into an input
for the model catalogue. Its models are **all free, with no usage cap** — the
list leads with DeepSeek:

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
│   ├── decision.py        # Typed decision protocols
│   └── tui.py             # Optional Textual terminal UI
├── providers/             # Provider implementations
│   ├── base.py            # Shared provider contract
│   ├── chatgpt/
│   ├── nvidia/
│   ├── openrouter/
│   ├── luna/
│   ├── ourfree/           # dsh-our-free-model local gateway
│   └── kilo/              # Kilo AI keyless free pool
├── examples/
│   └── questions.json     # Decision question example
├── config/
│   ├── providers.py       # Config load/save (user config dir)
│   └── providers.toml.example
├── docs/                  # Harness documentation
├── scripts/verify.sh      # Structural verification
└── CURRENTTASK            # Active objective tracker
```

`forks/` contains reference clones used during development and is excluded from
the release (see `.gitignore`).

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

MIT — see [LICENSE](LICENSE).


### Terminal workspace flow

The TUI opens on a centered composer. Ctrl+P opens a searchable provider
picker and Ctrl+M opens a searchable model picker. Selecting ChatGPT, Claude or
Gemini without credentials offers the matching account sign-in inside the TUI;
complete browser authorization and the model catalogue refreshes automatically.
Later or Escape
closes the dialog. An authorization already started continues in the background
until completion or timeout.

The right sidebar shows the active provider, model, conversation turns and
request status. Ctrl+B toggles it; narrow terminals start with it hidden.
Use `/connect`, `/models`, `/new`, `/sidebar`, or `/help` from the composer.
The layout follows the local OpenCode fork?s centered home, selection dialogs
and right session rail; codelaboon retains its own brand and Python runtime.


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
