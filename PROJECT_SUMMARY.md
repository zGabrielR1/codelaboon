# codelaboon - Project Summary

## Overview

**codelaboon** is a CLI harness for accessing free AI model access across multiple providers (ChatGPT, NVIDIA Nemotron, OpenRouter, Luna). It is similar to Freebuff but based on the PI harness principles. The project is designed to be CLI-only, cross-platform (Windows, macOS, Linux), and self-documenting.

## Key Features

### Architecture
- **Declarative Design**: Everything is self-documenting in the repo
- **Modular Architecture**: Clear separation of concerns between components
- **Provider-Agnostic**: Works with any free AI model provider
- **Cross-Platform**: Works on Windows, macOS, Linux without modification
- **Self-Describing**: All configuration and rules are in the repo
- **Minimal Dependencies**: Only essential dependencies are required

### CLI Interface
- **Provider Management**: List and configure AI model providers
- **Model Management**: List and use models for each provider
- **Chat Commands**: Send chat completion requests to models
- **Configuration Management**: Configure API keys and settings
- **Help System**: Comprehensive help for all commands

### Provider Support
- **ChatGPT**: OpenAI ChatGPT models (GPT-3.5 Turbo, GPT-4)
- **NVIDIA Nemotron**: NVIDIA's Nemotron models
- **OpenRouter**: Aggregator of multiple providers
- **Luna**: Luna AI models

### Configuration Management
- **TOML-based Configuration**: Centralized configuration management
- **API Key Management**: Secure API key storage and validation
- **Model Discovery**: Automatic model discovery and validation
- **Provider Configuration**: Provider-specific settings and parameters

### Documentation
- **Comprehensive Documentation**: Complete documentation for all components
- **PI Harness Principles**: Based on PI harness architectural principles
- **Self-Documenting**: Rules and behavior live in repo files, not in engineers' heads
- **API Documentation**: Complete API documentation for all components

## Project Structure

```
codelaboon/
├── README.md              # Project overview and setup instructions
├── codelaboon/            # Main CLI interface
│   ├── __init__.py       # Package initialization
│   └── cli.py            # Core CLI logic
├── providers/             # Model provider implementations
│   ├── __init__.py
│   ├── base.py           # Base provider interface
│   ├── chatgpt/          # ChatGPT provider
│   ├── nvidia/           # NVIDIA provider
│   ├── openrouter/       # OpenRouter provider
│   └── luna/             # Luna provider
├── config/                # Configuration management
│   ├── __init__.py
│   └── providers.py      # Provider configuration
├── docs/                  # Harness documentation
│   ├── AGENTS.md         # Agent roles and responsibilities
│   ├── ARCHITECTURE.md   # System architecture
│   ├── PROGRESS.md       # State tracking
│   ├── CURRENTTASK        # Active objective tracker
│   ├── Makefile          # Verification commands
│   ├── scripts/verify.sh # Structural verification
│   ├── UniversalMasterPromptDSL.md
│   ├── verifierAgentforUniversalMasterPromptAgent.md
│   ├── skillsLoader.md
│   └── utils/
│       ├── frameworkContinuousImprovement.md
│       ├── newSessionSummarizationOfContextOfFramework.md
│       ├── resumeOfLastTask.md
│       └── tokenCondensation.md
├── Makefile               # Verification commands
└── scripts/               # Utility scripts
    └── verify.sh          # Structural verification
```

## Key Components

### 1. CLI Interface (`codelaboon/cli.py`)
The main CLI interface provides:
- **Provider management**: List and configure AI model providers
- **Model management**: List and use models for each provider
- **Chat commands**: Send chat completion requests to models
- **Configuration management**: Configure API keys and settings
- **Help system**: Comprehensive help for all commands

### 2. Provider Framework (`providers/base.py`)
The base provider interface defines the contract for all AI model providers:
- **Abstract base class**: Defines the interface for all providers
- **Common methods**: `list_models()`, `chat()`, `validate_api_key()`
- **Extension points**: `_make_request()`, `_parse_response()`
- **Error handling**: Graceful error handling and recovery

### 3. Provider Implementations
Each provider implements the base interface:

#### ChatGPT Provider (`providers/chatgpt/chatgpt_provider.py`)
- **OpenAI API integration**: Integration with OpenAI's ChatGPT models
- **Model discovery**: Discovery of available ChatGPT models
- **API key validation**: Validation of API keys and quota
- **Error handling**: Robust error handling and recovery

#### NVIDIA Provider (`providers/nvidia/nvidia_provider.py`)
- **NVIDIA API integration**: Integration with NVIDIA Nemotron models
- **Model discovery**: Discovery of available NVIDIA models
- **API key validation**: Validation of API keys and quota
- **Error handling**: Robust error handling and recovery

#### OpenRouter Provider (`providers/openrouter/openrouter_provider.py`)
- **OpenRouter API integration**: Integration with OpenRouter aggregator
- **Model discovery**: Discovery of available OpenRouter models
- **API key validation**: Validation of API keys and quota
- **Error handling**: Robust error handling and recovery

#### Luna Provider (`providers/luna/luna_provider.py`)
- **Luna API integration**: Integration with Luna AI models
- **Model discovery**: Discovery of available Luna models
- **API key validation**: Validation of API keys and quota
- **Error handling**: Robust error handling and recovery

### 4. Configuration Management (`config/providers.py`)
TOML-based configuration management:
- **Centralized configuration**: Centralized configuration for all providers
- **API key management**: Secure API key storage and validation
- **Model discovery**: Automatic model discovery and validation
- **Provider configuration**: Provider-specific settings and parameters

### 5. Documentation
Comprehensive documentation following PI harness principles:

#### Core Documentation (`docs/`)
- **AGENTS.md**: Agent roles and responsibilities
- **ARCHITECTURE.md**: System architecture
- **PROGRESS.md**: State tracking
- **CURRENTTASK**: Active objective tracker

#### Harness Documentation
- **UniversalMasterPromptDSL.md**: Operator prompt
- **verifierAgentforUniversalMasterPromptAgent.md**: Verifier agent
- **skillsLoader.md**: Skills loader
- **arena.md**: Arena system

#### Utility Documentation (`docs/utils/`)
- **frameworkContinuousImprovement.md**: Continuous improvement system
- **newSessionSummarizationOfContextOfFramework.md**: Session context summarization
- **resumeOfLastTask.md**: State hydrator
- **tokenCondensation.md**: Context compactor

### 6. Verification (`Makefile` and `scripts/verify.sh`)
Built-in verification system:
- **Structure verification**: Verify project structure and file organization
- **Python syntax verification**: Verify Python syntax
- **Configuration verification**: Verify configuration files
- **Documentation verification**: Verify documentation files
- **Import verification**: Verify Python imports

## Project Philosophy

### PI Harness Principles
The project follows the PI harness principles:

1. **Declarative Design**: Everything is self-documenting in the repo
2. **Modular Architecture**: Clear separation of concerns between components
3. **Provider Agnosticism**: Works with any free AI model provider
4. **Cross-Platform**: Works on Windows, macOS, Linux without modification
5. **Self-Describing**: All configuration and rules are in the repo
6. **Minimal Dependencies**: Only essential dependencies are required

### Design Goals

1. **Simplicity**: Keep the design simple and minimal
2. **Extensibility**: Make it easy to add new providers
3. **Maintainability**: Make it easy to maintain and update
4. **Testability**: Make it easy to test and verify
5. **Documentation**: Document everything thoroughly

## Getting Started

### Prerequisites

- Python 3.11+
- `requests` library
- `requests` library
- `markdownlint-cli2` (optional)

### Installation

```bash
# Clone the repository
cd /path/to
codelaboon

# Run verification
make check

# Initialize configuration
make configure

# Add API keys to config/providers.toml
```

### Usage

#### Basic Commands

```bash
# List available providers
codelaboon providers list

# Get help for available commands
codelabeloon --help

# Configure a provider
codelaboon configure <provider>

# List models for a provider
codelaboon models list <provider>

# Send a chat request
codelaboon chat <provider> <model> <prompt>
```

#### Example Usage

```bash
# List all providers
codelaboon providers list

# List models for ChatGPT
codelaboon models list chatgpt

# Send a chat request to ChatGPT
codelaboon chat chatgpt "gpt-3.5-turbo" "Hello, how are you?"
```

### Verification

```bash
# Check structure and links
make check

# Lint Markdown documentation
make lint

# Full verification
make all
```

## Testing

The project includes comprehensive verification:

1. **Structure verification**: Verify project structure and file organization
2. **Python syntax verification**: Verify Python syntax
3. **Configuration verification**: Verify configuration files
4. **Documentation verification**: Verify documentation files
5. **Import verification**: Verify Python imports

## Future Development

### Planned Features

1. **New Providers**: Add support for new AI model providers
2. **Advanced Features**: Add advanced features like streaming responses
3. **Performance Improvements**: Optimize performance and resource usage
4. **Enhanced Documentation**: Improve documentation and examples
5. **Better Testing**: Add more comprehensive testing

### Future Directions

1. **Community Contributions**: Accept contributions from the community
2. **Integration with Other Tools**: Integrate with other development tools
3. **Cloud Deployment**: Deploy to cloud platforms
4. **Mobile Support**: Add mobile support
5. **Enterprise Features**: Add enterprise features

## Project Status

- **Architecture**: Complete
- **Core Implementation**: Complete
- **Provider Framework**: Complete
- **Documentation**: Complete for current scope
- **Verification**: Complete
- **Testing**: Offline unit and smoke tests
- **Dependencies**: Minimal (requests)

## License

This project is inspired by the PI harness and follows similar architectural principles. Licensed as appropriate for the underlying components.

## Contact

For questions or issues with codelaboon, please refer to the documentation or contact the maintainers.