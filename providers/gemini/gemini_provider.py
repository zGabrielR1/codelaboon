"""Google Gemini provider for codelaboon.

Two credential lanes share this provider:

- A Google AI Studio API key (``GEMINI_API_KEY`` / ``GOOGLE_API_KEY`` or the
  config file) uses the public ``generativelanguage.googleapis.com`` API.
- A Google account signed in with ``codelaboon login gemini`` uses the
  Antigravity OAuth token against the free Cloud Code Assist tier. This lane
  needs no billing account and no API key; Google onboards the account to the
  free tier automatically.

The free tier is the free-as-in-beer lane. Google's terms for that tier apply:
prompts may be processed, logged or retained by the provider according to the
tier's data policy. Use it for throwaway work, not secrets.
"""

import os
from typing import Any, Dict, List, Optional

import requests

from providers.base import BaseProvider

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
CLOUDCODE_BASE_URL = "https://daily-cloudcode-pa.googleapis.com"
API_VERSION = "v1internal"

DEFAULT_MODELS = [
    "gemini-4-argon",
    "gemini-3.8-flash",
    "gemini-3.1-pro-preview",
    "gemini-3.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]

# Model families the chat catalogue should not advertise.
_EXCLUDED = ("embedding", "imagen", "image", "veo", "aqa", "tts", "audio")


class GeminiProvider(BaseProvider):
    """Provider for Google Gemini models."""

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
        if (
            self.api_key.strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        ):
            return True
        from codelaboon.gemini_auth import read_session

        return bool(read_session())

    def _credential(self) -> tuple[str, str]:
        """Return ``(token, mode)`` where mode is ``api_key`` or ``oauth``."""
        key = (
            self.api_key.strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        )
        if key:
            return key, "api_key"
        if self.base_url != DEFAULT_BASE_URL:
            raise ValueError(
                "Gemini sign-in tokens can only be sent to Google."
            )
        from codelaboon.gemini_auth import access_token

        return access_token(), "oauth"

    @staticmethod
    def _headers(token: str, mode: str) -> Dict[str, str]:
        headers = {"content-type": "application/json"}
        if mode == "api_key":
            headers["x-goog-api-key"] = token
        else:
            from codelaboon.gemini_auth import user_agent

            headers["Authorization"] = f"Bearer {token}"
            headers["user-agent"] = user_agent()
            headers["x-goog-api-client"] = "gl-node/22.21.1"
        return headers

    @staticmethod
    def _catalogue_rows(rows: Any) -> tuple[List[str], Dict[str, str]]:
        """Normalize a catalogue response into ``(ids, display names)``."""
        models: List[str] = []
        names: Dict[str, str] = {}
        if isinstance(rows, dict):
            rows = [
                {"name": key, **value}
                for key, value in rows.items()
                if isinstance(value, dict)
            ]
        if not isinstance(rows, list):
            return models, names
        for row in rows:
            if not isinstance(row, dict):
                continue
            identifier = row.get("name") or row.get("id") or row.get("model")
            if not isinstance(identifier, str) or not identifier.strip():
                continue
            identifier = identifier.strip()
            if identifier.startswith("models/"):
                identifier = identifier[len("models/") :]
            if not identifier or any(part in identifier.lower() for part in _EXCLUDED):
                continue
            methods = row.get("supportedGenerationMethods")
            if isinstance(methods, list) and methods and "generateContent" not in methods:
                continue
            if identifier not in models:
                models.append(identifier)
                display = row.get("displayName") or row.get("display_name")
                if isinstance(display, str) and display.strip():
                    names[identifier] = display.strip()
        return models, names

    def _fallback_models(self) -> List[str]:
        return list(self.models or self.default_models)

    def list_models(self) -> List[str]:
        """List models visible to the account, with an offline fallback."""
        if not self.validate_api_key():
            return []
        token, mode = self._credential()
        if not token:
            return []

        if mode == "api_key":
            try:
                response = requests.get(
                    f"{self.base_url}/models",
                    headers=self._headers(token, mode),
                    params={"pageSize": 1000},
                    timeout=20,
                )
                if response.status_code == 200:
                    data = response.json()
                    rows = data.get("models") if isinstance(data, dict) else None
                    models, names = self._catalogue_rows(rows)
                    if models:
                        self.model_names = names
                        return models
                raise ValueError(
                    "Gemini model discovery failed. Check the API key and retry."
                )
            except requests.RequestException as error:
                raise ValueError(
                    "Cannot reach Gemini model discovery. "
                    "Check your connection and retry."
                ) from error

        from codelaboon.gemini_auth import project_id

        try:
            project = project_id()
        except (requests.RequestException, ValueError):
            project = ""
        if project:
            try:
                response = requests.post(
                    f"{CLOUDCODE_BASE_URL}/{API_VERSION}:fetchAvailableModels",
                    headers=self._headers(token, mode),
                    json={"project": project},
                    timeout=20,
                )
                if response.status_code == 200:
                    data = response.json()
                    rows = data.get("models") if isinstance(data, dict) else None
                    models, names = self._catalogue_rows(rows)
                    if models:
                        self.model_names = names
                        return models
            except (requests.RequestException, ValueError):
                pass  # Fall back to the pinned roster.
        return self._fallback_models()

    @staticmethod
    def _split_messages(
        messages: List[Dict[str, str]],
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Split system instructions from Gemini's user/model turns."""
        system_parts: List[str] = []
        contents: List[Dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                if isinstance(content, str) and content.strip():
                    system_parts.append(content)
                continue
            gemini_role = "model" if role == "assistant" else "user"
            if not isinstance(content, str):
                content = str(content)
            # Gemini expects alternating turns; merge adjacent same-role turns.
            if contents and contents[-1]["role"] == gemini_role:
                contents[-1]["parts"].append({"text": content})
            else:
                contents.append(
                    {"role": gemini_role, "parts": [{"text": content}]}
                )
        return "\n\n".join(system_parts), contents

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        if not self.validate_api_key():
            raise ValueError("Invalid or missing Gemini credential")
        token, mode = self._credential()
        if not token:
            raise ValueError("Gemini is not signed in")

        model = model.strip()
        if model.startswith("models/"):
            model = model[len("models/") :]

        system, contents = self._split_messages(messages)
        request: Dict[str, Any] = {"contents": contents}
        if system:
            request["systemInstruction"] = {"parts": [{"text": system}]}

        generation: Dict[str, Any] = {}
        max_tokens = kwargs.get("max_tokens")
        if max_tokens:
            generation["maxOutputTokens"] = int(max_tokens)
        temperature = kwargs.get("temperature")
        if temperature is not None:
            generation["temperature"] = temperature
        top_p = kwargs.get("top_p")
        if top_p is not None:
            generation["topP"] = top_p
        if generation:
            request["generationConfig"] = generation

        if mode == "api_key":
            url = f"{self.base_url}/models/{model}:generateContent"
            body = request
        else:
            from codelaboon.gemini_auth import project_id

            project = project_id()
            if not project:
                raise ValueError(
                    "Gemini free-tier project is missing. "
                    "Run codelaboon login gemini again."
                )
            url = f"{CLOUDCODE_BASE_URL}/{API_VERSION}:generateContent"
            body = {"model": model, "project": project, "request": request}

        try:
            response = requests.post(
                url,
                headers=self._headers(token, mode),
                json=body,
                timeout=kwargs.get("timeout", (15, 300)),
            )
        except requests.RequestException as error:
            raise ValueError(
                "Cannot reach Gemini. Check your connection and retry."
            ) from error

        if response.status_code != 200:
            if response.status_code in (401, 403):
                raise ValueError(
                    "Gemini rejected this account. The free tier is limited "
                    "by region and by Google's current terms; an API key is "
                    f"the alternative. (HTTP {response.status_code})"
                )
            if response.status_code == 429:
                raise ValueError(
                    "Gemini free-tier quota reached. Wait for the window to "
                    "reset or switch models."
                )
            raise ValueError(
                f"Gemini request failed (HTTP {response.status_code})."
            )
        return self._parse_response(response.json())

    def _make_request(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        return self.chat(model, messages, **kwargs)

    def _parse_response(self, response_data: Any) -> str:
        if not isinstance(response_data, dict):
            raise ValueError("Invalid response format: expected an object")
        # Cloud Code wraps the public GenerateContent response.
        payload = response_data.get("response")
        if isinstance(payload, dict) and "candidates" not in response_data:
            response_data = payload

        candidates = response_data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            feedback = response_data.get("promptFeedback")
            if isinstance(feedback, dict) and feedback.get("blockReason"):
                raise ValueError(
                    f"Gemini blocked the prompt ({feedback['blockReason']})."
                )
            raise ValueError("Invalid response format: no candidates")

        candidate = candidates[0]
        content = candidate.get("content") if isinstance(candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise ValueError("Invalid response format: no content parts")

        chunks: List[str] = []
        for part in parts:
            if not isinstance(part, dict) or part.get("thought"):
                continue
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
        if not chunks:
            raise ValueError("Gemini returned no text content")
        return "".join(chunks)
