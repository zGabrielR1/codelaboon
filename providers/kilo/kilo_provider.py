"""
Kilo provider for codelaboon.

Implements the BaseProvider interface against Kilo AI's public gateway
(https://kilo.ai), the same keyless free pool the dsh-our-free-model plugin
exposes as its Kilo channel. No account, no API key, no fingerprint gate: the
free pool answers with no credential at all.

Two properties of this lane shape the implementation:

- The roster is the listing's `isFree: true` slice. Everything else on the
  gateway is a paid id that answers 401 keyless, so the catalogue only ever
  broadcasts the free pool.
- The gateway is asked to stream (`stream: true`, `accept:
  text/event-stream`) but may answer with one JSON document under load, so
  the response is parsed by shape — SSE frames folded into one answer, or a
  single completion object — exactly like the reference client.

Models that declare a `reasoning` parameter take an effort level; "off" is
sent as `{"enabled": false}`. Some families (stepfun, liquid) refuse the off
rung with a 400 — their menus do not offer it upstream, and a refusal here is
surfaced as the API error it is.

Trade stated on the gateway's own model cards: free-pool prompts may be
logged by the upstream provider and used to improve its services. Use this
lane for throwaway work, not secrets.
"""

import json
import requests
from typing import List, Dict, Any, Optional
from providers.base import BaseProvider


DEFAULT_BASE_URL = "https://api.kilo.ai/api/gateway"

LISTING_TIMEOUT = 15
TURN_TIMEOUT = 300

EFFORT_LEVELS = ("off", "low", "medium", "high")


class KiloProvider(BaseProvider):
    """Provider for Kilo AI's keyless free model pool."""

    keyless = True

    def __init__(
        self,
        api_key: str,
        models: List[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Kilo provider.

        Args:
            api_key: Unused — the free pool needs no credential
            models: Optional pinned model list used when discovery is unavailable
            base_url: Gateway base URL override
        """
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        super().__init__(api_key, models)
        # The auto-routers are the pool's stable, always-free entry points;
        # every other free id is discovered live from the listing.
        self.default_models = ["kilo-auto/free", "openrouter/free"]

    def list_models(self) -> List[str]:
        """
        List the free pool: the listing's `isFree: true` rows.

        Falls back to the configured model list, then to the auto-routers,
        when the gateway cannot be reached.

        Returns:
            List of available model names
        """
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={"accept": "application/json", "user-agent": "codelaboon"},
                timeout=LISTING_TIMEOUT,
            )
            if response.status_code == 200:
                payload = response.json()
                rows = self._listing_rows(payload)
                models = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    model_id = row.get("id")
                    if row.get("isFree") is True and isinstance(model_id, str) and model_id.strip():
                        if model_id not in models:
                            models.append(model_id)
                if models:
                    return models
        except (requests.RequestException, ValueError):
            pass  # Fall back to the configured or default catalogue.

        if self.models:
            return self.models
        return self.default_models.copy()

    @staticmethod
    def _listing_rows(payload: Any) -> List[Any]:
        """Extract the listing rows from the envelope the gateway sends."""
        if isinstance(payload, dict):
            for key in ("data", "models"):
                if isinstance(payload.get(key), list):
                    return payload[key]
            return []
        if isinstance(payload, list):
            return payload
        return []

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to the free pool.

        Args:
            model: Free pool model id (paid ids answer 401 keyless)
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters; `reasoning` accepts "off",
                "low", "medium" or "high" for models that declare the
                parameter, and `timeout` bounds the turn (default 300s)

        Returns:
            String response from the model
        """
        data: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
        }

        reasoning = kwargs.get("reasoning")
        if reasoning is not None:
            if reasoning not in EFFORT_LEVELS:
                raise ValueError(
                    f"reasoning must be one of {', '.join(EFFORT_LEVELS)}"
                )
            data["reasoning"] = (
                {"enabled": False} if reasoning == "off" else {"effort": reasoning}
            )

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "content-type": "application/json",
                "accept": "text/event-stream",
                "user-agent": "codelaboon",
            },
            json=data,
            stream=True,
            timeout=kwargs.get("timeout", TURN_TIMEOUT),
        )

        if response.status_code != 200:
            raise Exception(
                f"API request failed: {response.status_code} - {response.text}"
            )

        return self._parse_stream_or_document(response)

    def _parse_stream_or_document(self, response: requests.Response) -> str:
        """
        Parse the reply by shape, not by Content-Type.

        The gateway may answer a stream request with SSE frames or with one
        JSON document. `:`-prefixed SSE lines are scheduling keepalives
        (`: KILO PROCESSING`) and are skipped.
        """
        chunks: List[str] = []
        stream_mode: Optional[bool] = None
        buffer = ""

        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if not chunk:
                continue
            if stream_mode is None:
                buffer = str(chunk)
                stripped = buffer.lstrip()
                stream_mode = stripped.startswith("data:") or stripped.startswith(":")
                if not stream_mode:
                    chunks.append(buffer)
                    buffer = ""
                continue
            if stream_mode:
                buffer += str(chunk)
            else:
                chunks.append(str(chunk))

        if stream_mode:
            return self._parse_sse(buffer)
        return self._parse_response(json.loads("".join(chunks)))

    @staticmethod
    def _parse_sse(body: str) -> str:
        """Fold SSE `data:` frames into one answer."""
        parts: List[str] = []
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith(":"):
                continue  # Keepalive comment, e.g. `: KILO PROCESSING`.
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("error"):
                error = event["error"]
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise Exception(f"API request failed: {message}")
            parts.append(KiloProvider._delta_text(event))
        return "".join(parts)

    @staticmethod
    def _delta_text(event: Any) -> str:
        """The text one stream event carries, or an empty string."""
        if not isinstance(event, dict):
            return ""
        choices = event.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        choice = choices[0] or {}
        delta = choice.get("delta") or {}
        piece = delta.get("content")
        if piece is None:
            piece = (choice.get("message") or {}).get("content")
        return piece if isinstance(piece, str) else ""

    def _make_request(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """Make API request (alias for chat method)."""
        return self.chat(model, messages, **kwargs)

    def _parse_response(self, response_data: Any) -> str:
        """
        Parse a single completion document.

        Args:
            response_data: Raw response data from the gateway

        Returns:
            Parsed string response
        """
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError("Invalid response format: no choices")

        choice = response_data["choices"][0]
        if "message" not in choice or "content" not in choice["message"]:
            raise ValueError("Invalid response format: no message content")

        return choice["message"]["content"]
