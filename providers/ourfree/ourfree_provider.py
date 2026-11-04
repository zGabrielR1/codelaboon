"""
Our Free Model provider for codelaboon.

Implements the BaseProvider interface against the local OpenAI-compatible
forward gateway exposed by the dsh-our-free-model plugin (DeepSeek Harness).

The gateway is the model catalogue input: `list_models()` discovers the live
roster from `GET /v1/models` so the catalogue follows the upstream refresh.
When the gateway is unreachable the provider falls back to the models pinned
in the configuration, and then to the built-in defaults.

Setup in the plugin (Settings -> Our Free Model -> Local Forwarding):
1. Enable the forward listener (it binds 127.0.0.1, port 18899 by default).
2. Copy the base URL and generate the API key (`ofm-...`).
3. Write both into the `[ourfree]` table of `providers.toml`.
"""

import requests
from typing import List, Dict, Any, Optional
from providers.base import BaseProvider


DEFAULT_BASE_URL = "http://127.0.0.1:18899/v1"


class OurFreeModelProvider(BaseProvider):
    """Provider for the dsh-our-free-model local forward gateway."""

    def __init__(
        self,
        api_key: str,
        models: List[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the Our Free Model provider.

        Args:
            api_key: Forward gateway key minted by the plugin (`ofm-...`)
            models: Optional pinned model list used when discovery is unavailable
            base_url: Forward gateway base URL; defaults to 127.0.0.1:18899/v1
        """
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        super().__init__(api_key, models)
        # The free lane's roster, DeepSeek first. Discovery from the gateway
        # supersedes this list whenever it is reachable; it is the offline
        # fallback so the catalogue still shows the models dsh provides.
        self.default_models = [
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
        ]

    def _headers(self) -> Dict[str, str]:
        """Build the headers the forward gateway expects."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def list_models(self) -> List[str]:
        """
        List available models.

        The live roster comes from the gateway (`GET /v1/models`), so the
        catalogue tracks upstream availability. Falls back to the configured
        model list, then to the built-in defaults, when the gateway cannot be
        reached or no key is configured.

        Returns:
            List of available model names
        """
        if self.validate_api_key():
            try:
                response = requests.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                    timeout=5,
                )
                if response.status_code == 200:
                    data = response.json().get("data", [])
                    models = [
                        row["id"] for row in data
                        if isinstance(row, dict) and row.get("id")
                    ]
                    if models:
                        return models
            except (requests.RequestException, ValueError):
                pass  # Fall back to the configured or default catalogue.

        if self.models:
            return self.models
        return self.default_models.copy()

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to the forward gateway.

        Args:
            model: Model name as broadcast by the gateway
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            String response from the model
        """
        if not self.validate_api_key():
            raise ValueError("Invalid or missing API key")

        # Prepare request data
        data = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0)
        }

        # Make API request
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json=data,
            timeout=kwargs.get("timeout", 60)
        )

        if response.status_code != 200:
            raise Exception(f"API request failed: {response.status_code} - {response.text}")

        # Parse response
        response_data = response.json()
        return self._parse_response(response_data)

    def _make_request(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """Make API request (alias for chat method)."""
        return self.chat(model, messages, **kwargs)

    def _parse_response(self, response_data: Any) -> str:
        """
        Parse the OpenAI-compatible gateway response.

        Args:
            response_data: Raw response data from the forward gateway

        Returns:
            Parsed string response
        """
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError("Invalid response format: no choices")

        choice = response_data["choices"][0]
        if "message" not in choice or "content" not in choice["message"]:
            raise ValueError("Invalid response format: no message content")

        return choice["message"]["content"]
