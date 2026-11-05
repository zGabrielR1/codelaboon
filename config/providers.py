"""
Provider configuration management for codelaboon.

Handles loading and saving provider configurations from TOML files.
"""

import json
import os
import tomllib
from pathlib import Path
from typing import Any, Dict


CONFIG_DIR = Path(os.environ.get("CODELABOON_CONFIG_DIR", str(Path.home() / ".config" / "codelaboon")))
PROVIDERS_CONFIG_FILE = CONFIG_DIR / "providers.toml"


def _default_config() -> Dict[str, Dict[str, Any]]:
    """Return the default (unconfigured) provider configuration."""
    return {
        "chatgpt": {
            "api_key": "",
            "models": [],
        },
        "nvidia": {
            "api_key": "",
            "models": ["nemotron-3"],
        },
        "openrouter": {
            "api_key": "",
            "models": ["openai/gpt-3.5-turbo"],
        },
        "luna": {
            "api_key": "",
            "models": ["luna-2"],
        },
        "ourfree": {
            "api_key": "",
            "base_url": "http://127.0.0.1:18899/v1",
            "models": [
                "deepseek-v4.1-flash-free",
                "deepseek-v4-flash-free",
                "glm-5.3-flash-free",
                "mimo-v2.6-flash-free",
                "mimo-v2.5-free",
                "nemotron-3-ultra-free",
                "nemotron-3.5-lightning-free",
                "ling-3.0-flash-fin-free",
                "space-bunny-free",
                "union-alpha",
                "muse-spark-1.3-contributor-free",
                "muse-spark-1.2-contributor-free",
                "jev-1.13-free",
            ],
        },
        "kilo": {
            "api_key": "",
            "models": ["kilo-auto/free", "openrouter/free"],
        },
    }


def _string_literal(value: str) -> str:
    """Encode a string as a TOML basic string."""
    return json.dumps(value, ensure_ascii=False)


def _dump_toml(config: Dict[str, Dict[str, Any]]) -> str:
    """Serialize the supported provider configuration to TOML."""
    lines = []
    for provider_name, provider_config in config.items():
        if not provider_name.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"Invalid provider name for TOML: {provider_name}")

        lines.append(f"[{provider_name}]")
        for key, value in provider_config.items():
            if isinstance(value, list):
                items = ", ".join(_string_literal(str(item)) for item in value)
                lines.append(f"{key} = [{items}]")
            elif isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, int):
                lines.append(f"{key} = {value}")
            elif isinstance(value, float):
                lines.append(f"{key} = {value}")
            else:
                lines.append(f"{key} = {_string_literal(str(value))}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_DIR.chmod(0o700)
    except OSError:
        pass


def get_providers_config() -> Dict[str, Dict[str, Any]]:
    """
    Get providers configuration from file.

    Creates a default (unconfigured) configuration if none exists.
    """
    if not PROVIDERS_CONFIG_FILE.exists():
        config = _default_config()
        save_providers_config(config)
        return config

    try:
        with open(PROVIDERS_CONFIG_FILE, "rb") as f:
            config = tomllib.load(f)

        if not isinstance(config, dict):
            raise ValueError("providers.toml must contain a table")

        # Ensure every known provider has the expected structure.
        for provider, values in _default_config().items():
            if provider not in config:
                config[provider] = dict(values)
                continue
            if not isinstance(config[provider], dict):
                config[provider] = dict(values)
                continue
            config[provider].setdefault("api_key", "")
            config[provider].setdefault("models", list(values["models"]))

        return config

    except (tomllib.TOMLDecodeError, ValueError, OSError) as e:
        print(f"Warning: Could not load providers config: {e}")
        return _default_config()


def save_provider_config(provider_name: str, config: Dict[str, Any]) -> bool:
    """
    Save configuration for a specific provider.

    Returns:
        True if successful, False otherwise
    """
    try:
        current_config = get_providers_config()
        current_config[provider_name] = config
        return save_providers_config(current_config)
    except Exception as e:
        print(f"Error saving provider config: {e}")
        return False


def save_providers_config(config: Dict[str, Dict[str, Any]]) -> bool:
    """
    Save providers configuration to file.

    Returns:
        True if successful, False otherwise
    """
    try:
        _ensure_config_dir()
        with open(PROVIDERS_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(_dump_toml(config))
        PROVIDERS_CONFIG_FILE.chmod(0o600)
        return True
    except Exception as e:
        print(f"Error saving providers config: {e}")
        return False


def get_default_models(provider_name: str) -> list:
    """Get default models for a provider."""
    defaults = {
        "chatgpt": [],
        "nvidia": ["nemotron-3"],
        "openrouter": ["openai/gpt-3.5-turbo"],
        "luna": ["luna-2"],
        "ourfree": [
            "deepseek-v4.1-flash-free",
            "deepseek-v4-flash-free",
        ],
        "kilo": ["kilo-auto/free", "openrouter/free"],
    }

    return defaults.get(provider_name, [])
