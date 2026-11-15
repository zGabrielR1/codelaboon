"""Pollinations provider for codelaboon.

Pollinations exposes a keyless, OpenAI-compatible text endpoint at
``https://text.pollinations.ai/openai``. The anonymous tier is genuinely free
(no account, no API key) and the catalogue is discovered from
``https://text.pollinations.ai/models``. An optional token can be configured
for higher tiers; it is sent as a bearer credential when present.

The anonymous pool is small and shared, so this lane is best treated as a
last-resort free provider: it fails over cleanly and reports rate limits
instead of hiding them. Prompts may be logged upstream under the free tier's
data policy; use it for throwaway work, not secrets.
"""

from typing import Any, Dict, List, Optional

import requests

from providers.base import BaseProvider


DEFAULT_BASE_URL = "https://text.pollinations.ai"
DEFAULT_MODELS = ["openai-fast"]
LISTING_TIMEOUT = 15
TURN_TIMEOUT = 90


class PollinationsProvider(BaseProvider):
    """Provider for Pollinations' keyless OpenAI-compatible text API."""

    keyless = True

    def __init__(
        self,
        api_key: str = "",
        models: List[str] = None,
        base_url: Optional[str] = None,
    ):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        super().__init__(api_key, models)
        self.default_models = list(DEFAULT_MODELS)

    def list_models(self) -> List[str]:
        """Discover the live text catalogue, falling back to configured rows."""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={
                    "accept": "application/json",
                    "user-agent": "codelaboon",
                },
                timeout=LISTING_TIMEOUT,
            )
            if response.status_code == 200:
                payload=response.json()
                if not isinstance(payload,list) and not (isinstance(payload,dict) and any(isinstance(payload.get(k),list) for k in ('data','models'))):
                    raise ValueError('Invalid model catalog')
                models: List[str] = []
                for row in self._listing_rows(payload):
                    if not isinstance(row, dict):
                        continue
                    name = row.get("name") or row.get("id")
                    modalities = row.get("output_modalities")
                    if isinstance(modalities, list) and "text" not in modalities:
                        continue
                    if isinstance(name, str) and name.strip() and name not in models:
                        models.append(name)
                self.live_models = list(models)
                self.discovery_error = None
                return models
            self.discovery_error = "http_" + str(response.status_code)
        except (requests.RequestException, ValueError) as error:
            self.discovery_error = type(error).__name__

        if self.models:
            return list(self.models)
        return list(self.default_models)

    @staticmethod
    def _listing_rows(payload: Any) -> List[Any]:
        """Extract rows from either a bare list or an object envelope."""
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "models"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        return []

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send one OpenAI-shaped chat completion request."""
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "codelaboon",
        }
        if self.api_key.strip():
            headers["authorization"] = f"Bearer {self.api_key.strip()}"

        body: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
        }
        timeout = kwargs.get("timeout", TURN_TIMEOUT)
        response = None
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{self.base_url}/openai",
                    headers=headers,
                    json=body,
                    timeout=timeout,
                )
                break
            except (requests.Timeout, requests.ConnectionError):
                # The anonymous pool is shared and occasionally stalls;
                # one immediate retry recovers most transient timeouts.
                if attempt:
                    raise
        if response is None:
            raise Exception("API request failed: no response")
        if response.status_code != 200:
            raise Exception(
                f"API request failed: {response.status_code} - {response.text[:400]}"
            )

        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            error = payload["error"]
            message = error.get("message") if isinstance(error, dict) else error
            raise Exception(f"API request failed: {message}")
        return self._parse_response(payload)

    def _make_request(
        self, model: str, messages: List[Dict[str, str]], **kwargs
    ) -> str:
        """Alias used by the shared harness."""
        return self.chat(model, messages, **kwargs)

    def _parse_response(self, response_data: Any) -> str:
        """Read the assistant text from an OpenAI completion document."""
        if not isinstance(response_data, dict):
            raise ValueError("Invalid response format: expected an object")
        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Invalid response format: no choices")
        choice = choices[0] or {}
        message = choice.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Invalid response format: no message content")
        return content
