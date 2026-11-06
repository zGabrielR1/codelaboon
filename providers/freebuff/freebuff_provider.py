"""Freebuff provider for codelaboon.

Freebuff (freebuff.com) is funded by ads instead of a subscription: a signed-in
account gets frontier coding models for free. Sign in with
``codelaboon login freebuff`` (device-code login — the same flow the Freebuff
CLI uses) and the free-session admission, model catalog and chat completions
run against the Codebuff API host.

The provider speaks the compiled (fallback) catalog: the picker rows the
Freebuff CLI ships, addressed by their plain wire model ids. That mode needs
no catalog handles and no device signing, exactly like an older Freebuff
client on a network that cannot fetch the server catalog. Models that exist
only in the server-driven catalog are not listed.

Free tier terms apply: prompts may be processed, logged or retained by the
provider under that tier's data policy, and some rows carry an explicit
AI-training notice. Use it for throwaway work, not secrets. Free sessions are
admitted per model for an hour; when the account is at a limit or a model is
withdrawn, the server's message is surfaced.

Credentials, in precedence order: the ``freebuff`` config table, then
``CODEBUFF_API_KEY`` / ``FREEBUFF_API_KEY``, then the
``codelaboon login freebuff`` session, then an installed Freebuff CLI's
``credentials.json``.
"""

import json
import os
import re
import threading
import uuid
from typing import Any, Dict, List, Optional

import requests

from providers.base import BaseProvider

DEFAULT_BASE_URL = "https://codebuff.com"
# Free sessions are admitted for an hour; completions bound above that.
TURN_TIMEOUT = 300

# Compiled picker rows (wire id, display name), most recommended first. This
# mirrors the Freebuff CLI's FREEBUFF_MODELS plus its fast-mode variant; the
# server remains the authority and answers withdrawn ids clearly.
FALLBACK_MODELS = [
    ("mimo/mimo-v2.5", "MiMo v2.6 Flash Fast"),
    ("z-ai/glm-5.3-flash", "GLM 5.3 Flash"),
    ("deepseek/deepseek-v4-flash", "DeepSeek V4.1 Flash 10/17"),
    ("deepseek/deepseek-v4-flash-fast", "DeepSeek V4.1 Flash Fast 10/17"),
    ("openai/gpt-6-luna", "GPT-6 Luna"),
    ("mimo/mimo-v2.6-pro", "MiMo 2.6 Pro"),
    ("upstage/solar-mini4", "Solar Mini 4"),
    ("upstage/solar-pro4", "Solar Pro 4"),
    ("google/gemini-3.8-flash", "Gemini 3.8 Flash"),
    ("meta/muse-spark-1.3-contributor", "Muse Spark 1.3"),
    ("google/gemini-4-argon", "Gemini 4 Argon"),
    ("openai/gpt-6.1-terra", "GPT-6.1 Terra"),
    ("openai/gpt-6.1-sol", "GPT-6.1 Sol"),
]
DEFAULT_MODELS = [model_id for model_id, _ in FALLBACK_MODELS]
MODEL_NAMES = dict(FALLBACK_MODELS)

# Session-gate rejections on POST /chat/completions, as (HTTP status). The
# server identifies the rejection by `error` code + `statusCode`; the prose
# message is rewritten freely, so codes are matched, never the message.
SESSION_EXPIRED_STATUSES = {409, 410}
SESSION_EXPIRED_CODES = {
    "session_expired",
    "session_superseded",
    "session_model_mismatch",
}

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean_text(value: Any, limit: int = 500) -> str:
    """Strip terminal escape sequences and bound the length."""
    if not isinstance(value, str):
        return ""
    text = _ANSI_ESCAPE.sub("", value)
    text = _CONTROL_CHARS.sub("", text)
    return " ".join(text.split())[:limit].strip()


class FreebuffProvider(BaseProvider):
    """Provider for Freebuff's free, ad-funded model catalog."""

    def __init__(
        self,
        api_key: str,
        models: List[str] = None,
        base_url: Optional[str] = None,
    ):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        super().__init__(api_key, models)
        self.default_models = list(DEFAULT_MODELS)
        self.model_names: Dict[str, str] = dict(MODEL_NAMES)
        self._slots: Dict[str, str] = {}
        self._lock = threading.RLock()

    def validate_api_key(self) -> bool:
        if self.api_key.strip():
            return True
        if os.environ.get("CODEBUFF_API_KEY", "").strip():
            return True
        if os.environ.get("FREEBUFF_API_KEY", "").strip():
            return True
        from codelaboon.freebuff_auth import token

        return bool(token())

    def _credential(self) -> tuple[str, str]:
        """Return ``(token, source)``; source is ``configured`` or ``account``."""
        value = self.api_key.strip()
        if value:
            return value, "configured"
        for name in ("CODEBUFF_API_KEY", "FREEBUFF_API_KEY"):
            value = os.environ.get(name, "").strip()
            if value:
                return value, "configured"
        if self.base_url != DEFAULT_BASE_URL:
            raise ValueError(
                "Freebuff sign-in tokens can only be sent to the Freebuff API."
            )
        from codelaboon.freebuff_auth import access_token

        return access_token(), "account"

    @staticmethod
    def _instance_id() -> str:
        """Mint one instance per model for this process (``cli:<uuid>``)."""
        return "cli:" + str(uuid.uuid4())

    def list_models(self) -> List[str]:
        """List the compiled catalog, with configured models taking precedence."""
        if not self.validate_api_key():
            return []
        if self.models:
            return list(self.models)
        return list(DEFAULT_MODELS)

    def _admission_headers(self, token: str, wire_model: str, instance_id: str) -> Dict[str, str]:
        from codelaboon import __version__

        attempt = instance_id[4:] if instance_id.startswith("cli:") else ""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "x-freebuff-instance-id": instance_id,
            "x-freebuff-model": wire_model,
            "x-freebuff-wallet-spend-limit": "session",
            "x-freebuff-client": "cli",
            "x-freebuff-client-version": __version__,
        }
        if attempt:
            headers["x-freebuff-multi-session"] = "1"
            headers["x-freebuff-purchase-continuity"] = "1"
            headers["x-freebuff-desktop-attempt-id"] = attempt
        return headers

    @staticmethod
    def _server_message(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        return _clean_text(payload.get("message"), 400)

    def _admit(self, token: str, wire_model: str, instance_id: str) -> str:
        """POST a free-session admission; return the live instance id."""
        response = requests.post(
            f"{self.base_url}/api/v1/freebuff/session/admission",
            headers=self._admission_headers(token, wire_model, instance_id),
            timeout=30,
        )
        if response.status_code == 404:
            raise ValueError(
                "This Freebuff server cannot start a session yet. "
                "Reload or update Freebuff and try again shortly."
            )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code in (401, 403):
            detail = self._server_message(payload)
            raise ValueError(
                detail or "Freebuff rejected this account. Sign in again with "
                "`codelaboon login freebuff`."
            )
        if not isinstance(payload, dict) or not payload.get("status"):
            detail = self._server_message(payload)
            raise ValueError(
                detail
                or "Freebuff did not admit a session. "
                f"(HTTP {response.status_code})"
            )
        status = str(payload.get("status") or "")
        detail = self._server_message(payload)
        if status == "active":
            live = payload.get("instanceId")
            return str(live) if isinstance(live, str) and live else instance_id
        if status == "ended" and payload.get("instanceId"):
            # Inside the server grace window: completions still flow so an
            # in-flight turn can finish.
            live = payload.get("instanceId")
            return str(live) if isinstance(live, str) and live else instance_id
        if status == "country_blocked":
            raise ValueError(
                detail
                or "Freebuff free mode is not available in your country. "
                "Try another connection or the web app."
            )
        if status == "model_unavailable":
            raise ValueError(
                detail or "This Freebuff model was withdrawn from free mode. "
                "Choose another model."
            )
        if status == "rate_limited":
            raise ValueError(
                detail or "This Freebuff model is rate limited right now. "
                "Wait or choose another model."
            )
        if status == "spend_limited":
            raise ValueError(
                detail or "This Freebuff model's free allowance is spent. "
                "Wait for the reset or choose another model."
            )
        raise ValueError(
            detail
            or f"Freebuff did not admit a session ({status}). "
            "Try again shortly."
        )

    def _ensure_slot(self, token: str, wire_model: str) -> str:
        """Return a live instance id for this wire model, admitting if needed."""
        with self._lock:
            live = self._slots.get(wire_model)
        if live:
            return live
        instance_id = self._instance_id()
        live = self._admit(token, wire_model, instance_id)
        with self._lock:
            self._slots[wire_model] = live
        return live

    def _drop_slot(self, wire_model: str) -> None:
        with self._lock:
            self._slots.pop(wire_model, None)

    @staticmethod
    def _completion_body(
        model: str,
        messages: List[Dict[str, str]],
        instance_id: str,
        kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", 0.7),
            "codebuff_metadata": {
                "run_id": str(uuid.uuid4()),
                "client_id": str(uuid.uuid4()),
                "cost_mode": "free",
                "freebuff_instance_id": instance_id,
                "freebuff_multi_session": "1",
                "surface": "cli",
            },
            "provider": {"allow_fallbacks": True},
        }
        if kwargs.get("reasoning_effort") is not None:
            body["reasoning_effort"] = kwargs["reasoning_effort"]
        if kwargs.get("stop") is not None:
            body["stop"] = kwargs["stop"]
        return body

    def _post_completion(
        self, token: str, body: Dict[str, Any], timeout: Any
    ) -> "requests.Response":
        from codelaboon import __version__

        return requests.post(
            f"{self.base_url}/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "user-agent": f"codelaboon/{__version__}",
                "x-freebuff-client-version": __version__,
            },
            json=body,
            timeout=timeout,
        )

    def _completion_error(self, response: "requests.Response") -> ValueError:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        code = payload.get("error") if isinstance(payload, dict) else None
        detail = self._server_message(payload)
        if response.status_code == 401:
            return ValueError(
                detail or "Freebuff rejected this token. "
                "Run `codelaboon login freebuff` again."
            )
        if response.status_code == 429:
            if code == "free_mode_capacity_deferred":
                return ValueError(
                    detail or "Freebuff is at capacity for free mode. "
                    "Wait and retry."
                )
            return ValueError(
                detail or "Freebuff rate limit reached. Wait and retry."
            )
        if code in ("waiting_room_required", "waiting_room_queued"):
            return ValueError(
                detail or "Freebuff is in its waiting room. Wait and retry."
            )
        if code == "session_limit_reached":
            return ValueError(
                detail or "This Freebuff account already has a live session. "
                "Close it or wait for it to end."
            )
        if code == "model_unavailable":
            return ValueError(
                detail or "This Freebuff model was withdrawn from free mode. "
                "Choose another model."
            )
        return ValueError(detail or f"Freebuff request failed (HTTP {response.status_code}).")

    def _is_session_gone(self, response: "requests.Response") -> bool:
        if response.status_code not in SESSION_EXPIRED_STATUSES:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        return (
            isinstance(payload, dict)
            and payload.get("error") in SESSION_EXPIRED_CODES
        )

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.validate_api_key():
            raise ValueError("Invalid or missing Freebuff credential")
        token, _source = self._credential()
        if not token:
            raise ValueError("Freebuff is not signed in")

        wire_model = str(model or "").strip()
        if not wire_model:
            raise ValueError("Freebuff needs a model name")

        timeout = kwargs.get("timeout", TURN_TIMEOUT)
        instance_id = self._ensure_slot(token, wire_model)
        body = self._completion_body(wire_model, messages, instance_id, kwargs)
        response = self._post_completion(token, body, timeout)

        if self._is_session_gone(response):
            # The server ended the slot: re-admit on a fresh instance and
            # retry once, rather than failing the turn.
            self._drop_slot(wire_model)
            instance_id = self._ensure_slot(token, wire_model)
            body = self._completion_body(
                wire_model, messages, instance_id, kwargs
            )
            response = self._post_completion(token, body, timeout)

        if response.status_code != 200:
            raise self._completion_error(response)

        try:
            payload = response.json()
        except ValueError as error:
            raise ValueError("Freebuff returned an invalid response.") from error
        return self._parse_response(payload)

    def _parse_response(self, response_data: Any) -> str:
        """Parse the OpenAI-compatible completions response."""
        if not isinstance(response_data, dict):
            raise ValueError("Invalid response format: no choices")
        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Invalid response format: no choices")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("Invalid response format: no choices")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("Invalid response format: no message content")
        content = message.get("content")
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            if parts:
                return "".join(parts)
        for key in ("reasoning_content", "reasoning", "reasoningDetails"):
            value = message.get(key)
            if isinstance(value, str) and value:
                return value
        return ""
