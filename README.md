# codelaboon

**A CLI harness for accessing AI models from multiple providers**

codelaboon is a cross-platform, CLI-first harness for calling AI models through
their provider APIs. It works from source with no installation step, and can
optionally be installed as a `codelaboon` command.

## Overview

codelaboon follows PI harness principles:

- **CLI-first**: no web UI, no interactive prompts required
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
```

A safe template is available in [`config/providers.toml.example`](config/providers.toml.example).
**Never commit real API keys** — the real `config/providers.toml` is gitignored.

Then:

```bash
python3 -m codelaboon providers list
python3 -m codelaboon models list chatgpt
python3 -m codelaboon chat openrouter openai/gpt-3.5-turbo "Hello"
```

## Installation (optional)

```bash
python3 -m pip install --user .
codelaboon providers list
```

This installs a `codelaboon` console script and the Python packages used by the
harness. Running from the source checkout works without installing.

## Commands

| Command | Description |
|---------|-------------|
| `providers list` | List providers and whether they are configured |
| `models list <provider>` | List models for a provider |
| `chat <provider> <model> <prompt>` | Send a chat completion request |
| `configure <provider>` | Interactively write an API key to the config |
| `doctor` | Diagnose Python, dependencies, providers and config |

Common options for `chat`: `--system`, `--temperature`, `--max-tokens`.

```bash
python3 -m codelaboon chat openrouter my-model "Hello" --temperature 0.2 --max-tokens 200
```

## Supported providers

- **ChatGPT / OpenAI** (`chatgpt`) — OpenAI-compatible chat completions
- **NVIDIA Nemotron** (`nvidia`) — NVIDIA hosted endpoints
- **OpenRouter** (`openrouter`) — multi-provider aggregator
- **Luna** (`luna`) — Luna AI endpoints

Each provider implements the shared contract in [`providers/base.py`](providers/base.py).
API keys, base URLs, default models and request payloads are provider-specific;
check the provider module you are using.

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
│   └── cli.py
├── providers/             # Provider implementations
│   ├── base.py            # Shared provider contract
│   ├── chatgpt/
│   ├── nvidia/
│   ├── openrouter/
│   └── luna/
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
