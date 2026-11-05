"""Anthropic Claude provider for codelaboon.

Two credential lanes share this provider:

- An Anthropic API key (``ANTHROPIC_API_KEY`` or the config file) uses the
  normal ``x-api-key`` Messages API.
- A claude.ai account signed in with ``codelaboon login claude`` uses the
  Claude Code OAuth token with ``Authorization: Bearer``. This is what carries
  Pro, Max, Ultra, Team and Enterprise plan entitlement.

A free claude.ai account can complete the same sign-in, but Anthropic does not
currently include Claude Code or API inference with the free plan. When the
account has no allowance the provider surfaces Anthropic's own plan error. The
free-as-in-beer lanes remain Gemini's Google-account login, ``ourfree`` and
``kilo``.
"""

import os
from typing import Any, Dict, List, Optional

import requests

from providers.base import BaseProvider

DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
OAUTH_BETA = "oauth-2025-04-20,claude-code-20250219"
CLAUDE_CODE_USER_AGENT = "claude-cli/2.1.293 (external, cli)"

DEFAULT_MODELS = [
    "claude-sonnet-5-5",
    "claude-opus-5-5",
    "claude-haiku-5-5",
    "claude-fable-5-1",
    "claude-sonnet-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
]


class ClaudeProvider(BaseProvider):
    """Provider for Anthropic Claude models."""

    def __init__(
        self,
        api_key: str,
        models: List[str] = None,
        base_url: Optional[str] = None,
    ):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        super().__init__(api_key, models)
        self.default_models = list(DEFAULT_MODELS)
        self.model_names: Dict[str, str] = {}

    def validate_api_key(self) -> bool:
        if self.api_key.strip() or os.environ.get("ANTHROPIC_API_KEY", "").strip():
            return True
        from codelaboon.claude_auth import read_session

        return bool(read_session())

    def _credential(self) -> tuple[str, str]:
        """Return ``(token, mode)`` where mode is ``api_key`` or ``oauth``."""
        key = self.api_key.strip() or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if key:
            return key, "api_key"
        if self.base_url != DEFAULT_BASE_URL:
            raise ValueError(
                "Claude sign-in tokens can only be sent to Anthropic."
            )
        from codelaboon.claude_auth import access_token

        return access_token(), "oauth"

    @staticmethod
    def _headers(token: str, mode: str) -> Dict[str, str]:
        headers = {
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        if mode == "api_key":
            headers["x-api-key"] = token
        else:
            headers["Authorization"] = f"Bearer {token}"
            headers["anthropic-beta"] = OAUTH_BETA
            headers["x-app"] = "cli"
            headers["user-agent"] = CLAUDE_CODE_USER_AGENT
        return headers

    def list_models(self) -> List[str]:
        """List models visible to the account, with an offline fallback."""
        if not self.validate_api_key():
            return []
        token, mode = self._credential()
        if not token:
            return []
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self._headers(token, mode),
                params={"limit": 1000},
                timeout=20,
            )
            if response.status_code == 200:
                data = response.json()
                rows = data.get("data") if isinstance(data, dict) else None
                if isinstance(rows, list):
                    models: List[str] = []
                    names: Dict[str, str] = {}
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        model_id = row.get("id")
                        if not isinstance(model_id, str) or not model_id.strip():
                            continue
                        model_id = model_id.strip()
                        if model_id not in models:
                            models.append(model_id)
                            display = row.get("display_name")
                            if isinstance(display, str) and display.strip():
                                names[model_id] = display.strip()
                    if models:
                        self.model_names = names
                        return models
            if mode == "oauth":
                # Claude Code's account catalogue is not always exposed at
                # /v1/models. The pinned roster is the safe fallback.
                return list(self.models or self.default_models)
            raise ValueError(
                "Claude model discovery failed. Check the API key and retry."
            )
        except requests.RequestException as error:
            if mode == "oauth":
                return list(self.models or self.default_models)
            raise ValueError(
                "Cannot reach Claude model discovery. Check your connection."
            ) from error

    @staticmethod
    def _split_messages(messages: List[Dict[str, str]]) -> tuple[str, List[Dict[str, str]]]:
        system_parts: List[str] = []
        turns: List[Dict[str, str]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                if isinstance(content, str) and content.strip():
                    system_parts.append(content)
                continue
            if role in ("user", "assistant"):
                turns.append({"role": role, "content": content})
        return "\n\n".join(system_parts), turns

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.validate_api_key():
            raise ValueError("Invalid or missing Claude credential")
        token, mode = self._credential()
        if not token:
            raise ValueError("Claude is not signed in")

        system, turns = self._split_messages(messages)
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "messages": turns,
            "stream": False,
        }
        if system:
            body["system"] = system
        if "temperature" in kwargs and kwargs["temperature"] is not None:
            body["temperature"] = kwargs["temperature"]

        try:
            response = requests.post(
                f"{self.base_url}/messages",
                headers=self._headers(token, mode),
                json=body,
                timeout=kwargs.get("timeout", (15, 300)),
            )
        except requests.RequestException as error:
            raise ValueError(
                "Cannot reach Claude. Check your connection and retry."
            ) from error

        if response.status_code != 200:
            if response.status_code in (401, 403):
                raise ValueError(
                    "Claude rejected this account for inference. Pro, Max, "
                    "Ultra, Team and Enterprise plans include Claude Code; "
                    "the free plan does not. The provider decides what its "
                    f"free tier includes. (HTTP {response.status_code})"
                )
            if response.status_code == 429:
                raise ValueError(
                    "Claude plan usage limit reached. Wait for the window to "
                    "reset or switch models."
                )
            raise ValueError(
                f"Claude request failed (HTTP {response.status_code})."
            )
        return self._parse_response(response.json())

    def _make_request(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        return self.chat(model, messages, **kwargs)

    def _parse_response(self, response_data: Any) -> str:
        if not isinstance(response_data, dict):
            raise ValueError("Invalid response format: expected an object")
        content = response_data.get("content")
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            raise ValueError("Invalid response format: no content")
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") in ("thinking", "redacted_thinking", "tool_use"):
                continue
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
        if not parts and content:
            raise ValueError("Claude returned no text content")
        return "".join(parts)
