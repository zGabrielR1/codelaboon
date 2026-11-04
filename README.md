# codelaboon

**A CLI harness for accessing AI models from multiple providers**

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
| `configure <provider>` | Interactively write an API key to the config |
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

- **ChatGPT / OpenAI** (`chatgpt`) — OpenAI-compatible chat completions
- **NVIDIA Nemotron** (`nvidia`) — NVIDIA hosted endpoints
- **OpenRouter** (`openrouter`) — multi-provider aggregator
- **Luna** (`luna`) — Luna AI endpoints
- **Our Free Model** (`ourfree`) — the local forward gateway of the
  [dsh-our-free-model](https://github.com/Ebony-Vinyl/dsh-our-free-model)
  plugin for DeepSeek Harness

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
│   └── ourfree/           # dsh-our-free-model local gateway
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
