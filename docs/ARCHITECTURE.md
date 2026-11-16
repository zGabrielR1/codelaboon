# ARCHITECTURE — codelaboon

The default terminal now executes a pinned OpenCode source fork. An alternate
Oh My Pi source engine shares the Python provider gateway. Source bundles include
licenses and provenance; dependencies and credentials are runtime-only. The gateway
preserves tools and streaming in chat/Responses/Anthropic/Google protocols.
See [native runtime architecture and operations](native-runtime.md) for the current
UI, free routing, local/security profiles, installation and OS-managed workers.
The older Textual implementation below remains a reference implementation.

RC21 security execution separates explicit-scope networking and evidence
collection (`security_assessment.py`) from pure response rules
(`security_checks.py`), bounded explicit-file IT auditing (`security_local.py`)
and defensive retest comparison (`security_reports.py`). The security profile
guides hypotheses and evidence review; deterministic runner checks enforce the
approved network scope and budgets. See [usage and limits](rc21-security.md).

A declarative prompt-engineering harness for free AI model access. It wraps free model access into a self-perpetuating lifecycle: any CLI session bootstraps state, operates under a master prompt, verifies adversarially, improves the provider configurations themselves, and condenses context for the next session.

Python source code with a small runtime dependency set (`requests` and PyJWT;
Textual is optional) and no build service.

## Layout

```text
codelaboon/
├── README.md              # This documentation
├── codelaboon/            # Main CLI interface
│   ├── __init__.py       # Package initialization
│   ├── cli.py            # Core CLI logic
│   ├── decision.py       # Typed decision protocols
│   ├── chatgpt_auth.py   # ChatGPT account sign-in
│   ├── claude_auth.py    # Claude account sign-in
│   ├── gemini_auth.py    # Gemini/Google account sign-in
│   ├── freebuff_auth.py  # Freebuff device-code sign-in
│   ├── qoder_auth.py     # Qoder browser device sign-in
│   ├── free_auto.py      # free (Auto) ranking and failover
│   ├── install.py        # `codelaboon install` (pip + PATH)
│   ├── update.py         # `codelaboon update` (pull + reinstall)
│   └── tui.py            # CLI TUI (default interface)
├── providers/             # Model provider implementations
│   ├── __init__.py
│   ├── base.py           # Base provider interface
│   ├── chatgpt/          # ChatGPT/OpenAI provider
│   ├── claude/           # Anthropic Claude provider
│   ├── gemini/           # Google Gemini provider
│   ├── freebuff/         # Freebuff ad-funded free-tier provider
│   ├── qoder/            # Qoder free-plan provider (official CLI print mode)
│   ├── nvidia/           # NVIDIA Nemotron provider
│   ├── openrouter/       # OpenRouter provider
│   ├── luna/             # Luna provider
│   ├── ourfree/          # dsh-our-free-model local gateway provider
│   ├── kilo/             # Kilo AI keyless free-pool provider
│   └── pollinations/     # Pollinations keyless text provider
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

RC15 separates the lean core, engine assets and external development trees.
OpenCode remains the interactive default; native Jcode handles bounded swarms and
background building. See [lean runtime operations](lean-runtime.md).


### RC22 task operations
`task_api.py` exposes authenticated loopback queue/control/conversation endpoints through `web.py`; `static/tasks.*` renders task conversations and policy. `task_conversation.py` persists human messages under hashed task control directories and appends bounded guidance at `watch.py` attempt checkpoints. Inclusion receipts identify prompt capture, not model acknowledgement. Privileged snapshots never read live guidance. `engine_tasks.py` provides the portable coordinator adapters; `work_monitor.py` projects real scheduler attempts and logs. `runtime_management.py` and `release_update.py` implement cache health, repair receipts and verified installed-wheel updates.


### RC24 execution configuration
`task_settings.py` persists per-task optimistic revisions under task controls and projects a copy at each scheduler checkpoint; initial settings may be captured inside the atomic inbox record. `watch.py` snapshots values into each attempt, optionally invokes a bounded `task_orchestrator.py` planning subprocess, then dispatches the worker and independent checks within the same budget. `native_gateway.py` applies captured additive system instructions in the native wire protocol and pins delegated task requests to the selected worker model. Local planning directly calls only the configured loopback local provider. `task_changes.py` provides read-only bounded Git evidence; pre/post fingerprints record observed filenames without claiming exclusive agent authorship. Browser APIs and terminal/CLI controls share the same revisioned configuration plane.
