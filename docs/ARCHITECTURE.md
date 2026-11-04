# ARCHITECTURE — codelaboon

A declarative prompt-engineering harness for free AI model access. It wraps free model access into a self-perpetuating lifecycle: any CLI session bootstraps state, operates under a master prompt, verifies adversarially, improves the provider configurations themselves, and condenses context for the next session.

No code, no build system, no runtime dependencies. Everything is self-documenting plain text and Python source code.

## Layout

```text
codelaboon/
├── README.md              # This documentation
├── codelaboon/            # Main CLI interface
│   ├── __init__.py       # Package initialization
│   ├── cli.py            # Core CLI logic
│   ├── decision.py       # Typed decision protocols
│   └── tui.py            # Optional Textual terminal UI
├── providers/             # Model provider implementations
│   ├── __init__.py
│   ├── base.py           # Base provider interface
│   ├── chatgpt/          # ChatGPT/OpenAI provider
│   ├── nvidia/           # NVIDIA Nemotron provider
│   ├── openrouter/       # OpenRouter provider
│   ├── luna/             # Luna provider
│   └── ourfree/          # dsh-our-free-model local gateway provider
├── config/                # Configuration management
│   ├── __init__.py
│   └── providers.py      # Provider configuration
├── docs/                  # Harness documentation
│   ├── AGENTS.md         # Agent roles and responsibilities
│   ├── ARCHITECTURE.md   # System map (this file)
│   ├── PROGRESS.md       # State tracking
│   ├── CURRENTTASK        # Active objective tracker
│   ├── Makefile          # Feedback subsystem
│   └── scripts/verify.sh # Structural verification
│   └── UniversalMasterPromptDSL.md
│   └── verifierAgentforUniversalMasterPromptAgent.md
│   └── utils/
│       ├── newSessionSummarizationOfContextOfFramework.md
│       ├── resumeOfLastTask.md
│       ├── frameworkContinuousImprovement.md
│       └── tokenCondensation.md
├── Makefile               # Verification commands
└── scripts/               # Utility scripts
    └── verify.sh          # Structural verification
```

## The lifecycle (context flow)

`Bootstrap` → `Operator` → `GLUE` → (`Resume` if past state) → `Thinking` → `Task Spec` → `Verifier` → `Improvement` → `Condensation` → (next session `Bootstrap`).

Routing rules, context budgets (32k recon / 8k worker / 16k adversarial review / 32k synthesis token tiers), artifact exchange schema (`REG_INSTRUCTURE`, `REG_STATE_VARS`, `REG_BIAS_LOG`, `REG_AST_DELTAS`), and the response telemetry contract are owned by `docs/glue.md`.

Step 5 is single-path by default. When `docs/arena.md` §2 fires, it expands into an arena run — N independent operator instances on one locked task, then a verifier acting as judge over anonymized candidates. Fan-out is a mode of the existing lifecycle, not a sixth subsystem: it reuses the operator and the verifier and adds no new stage.

## Five harness subsystems

| Subsystem | File(s) | Role |
|-----------|---------|------|
| Instruction | `docs/AGENTS.md` | Project overview, structure map, workflow, hard constraints |
| State | `PROGRESS.md`, `CURRENTTASK` | Done/in-progress/blocked tracking; objective continuity across sessions |
| Feedback | `Makefile`, `scripts/verify.sh` | Executable verification (structure, links, referential integrity) |
| Environment | (repo root layout + `Makefile`) | Dependency-free by design; nothing to install, no runtime drift |
| Tool | (agent runtime) | Keep the agent's native file/shell tool access per least privilege |

`docs/AGENTS.md` answers: what is this system, how is it organized, how do I run it, how do I verify it, where are we now. A fresh session can start work without asking a human.

## Execution substitutes

- The GLUE orchestrator and operator/verifier prompts are declared in `docs/`.
- `CURRENTTASK` is the objective; `PROGRESS.md` is the state; both are read at CLI start.
- Provider mutations flow through `docs/utils/frameworkContinuousImprovement.md` as diffs, never by ad-hoc rewrites (provider configurations are treated as source).

## Operational priorities

1. Keep `docs/AGENTS.md` a ~100-line map, not a manual — push depth into `docs/`.
2. Keep rules only in repo files so the CLI can see them.
3. Keep the model fixed when ablating subsystems; remove one subsystem at a time to measure marginal contribution for the current task.

## Provider Architecture

The provider architecture follows a clear pattern:

### BaseProvider Interface
- **Abstract base class** defining the contract for all AI model providers
- **Common methods**: `list_models()`, `chat()`, `validate_api_key()`
- **Extension points**: `_make_request()`, `_parse_response()`

### Provider Implementations
- Each provider implements the base interface
- Provider-specific API endpoints, authentication, and response parsing
- Consistent error handling and validation

### Configuration Management
- TOML-based configuration
- Provider-specific settings (API keys, model lists)
- Automatic model discovery and validation

### CLI Integration
- Unified command interface for all providers
- Consistent argument parsing and help text
- Provider-agnostic command structure

## Cross-Platform Design

The harness is designed for cross-platform operation:

- **Python Native**: Uses Python's built-in cross-platform support
- **Path Handling**: Uses `pathlib.Path` for platform-independent path operations
- **File System**: No platform-specific assumptions
- **Network Requests**: Uses `requests` library with platform-agnostic HTTP
- **Configuration**: Uses TOML for platform-independent configuration

## Dependencies Management

The harness follows strict dependency management principles:

- **No external build systems**: Only Python standard library + `requests`
- **Self-contained**: Everything needed is in the repo
- **No runtime drift**: Same behavior across environments
- **Minimal dependencies**: Each provider only depends on what's needed

## Verification Integration

The harness integrates verification throughout:

- **Structure verification**: `make check` validates file structure and links
- **Configuration verification**: Validates API keys and provider settings
- **Functionality verification**: Tests provider connectivity and model access
- **Documentation verification**: Ensures all required files are present

## Engineering Principles Applied

1. **Declarative Design**: Rules and behavior are defined in source files, not in engineers' heads
2. **Modular Architecture**: Clear separation of concerns between components
3. **Provider Agnosticism**: Works with any free AI model provider
4. **Cross-Platform**: Same functionality across Windows, macOS, and Linux
5. **Self-Describing**: All configuration and rules are in the repo
6. **Minimal Dependencies**: Only essential dependencies are required
7. **Testable**: Each component can be tested independently
8. **Documented**: Comprehensive documentation for all components

## Provider-Specific Considerations

Each provider implements:

- **Authentication**: Provider-specific API key validation
- **Model Discovery**: Listing and testing available models
- **API Integration**: Making chat completion requests
- **Response Parsing**: Converting API responses to string output
- **Error Handling**: Graceful handling of API errors

The harness abstracts these provider-specific details while maintaining provider-specific functionality.

## Future Extensibility

The architecture is designed for easy extension:

- **New Providers**: Add new provider directory with implementation
- **New Features**: Extend CLI with new commands
- **New Configuration**: Add new configuration options
- **New Documentation**: Add new documentation files
- **New Verification**: Add new verification checks

Each extension follows the existing patterns and conventions.