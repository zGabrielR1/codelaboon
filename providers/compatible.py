"""Live OpenAI-compatible catalogues, including a strictly free OpenRouter lane."""
import os
from urllib.parse import urlsplit

import requests

from providers.base import BaseProvider


class CompatibleProvider(BaseProvider):
    base_url = ""
    environment = ""
    transport = requests

    def credential(self):
        return self.api_key.strip() or os.environ.get(self.environment, "").strip()

    def validate_api_key(self):
        return self.keyless or bool(self.credential())

    def headers(self):
        return {"Authorization": f"Bearer {self.credential()}"} if self.credential() else {}

    def list_models(self):
        if not self.validate_api_key():
            return []
        try:
            with self.transport.get(self.base_url.rstrip("/") + "/models", headers=self.headers(), timeout=10, allow_redirects=False) as response:
                response.raise_for_status()
                rows = response.json()["data"]
                models = list(dict.fromkeys(row["id"] for row in rows
                              if isinstance(row, dict) and isinstance(row.get("id"), str)
                              and self.accepts(row)))
                return models
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return [model for model in self.models if self.accepts({"id": model})]

    def accepts(self, row):
        return True

    def chat(self, model, messages, **kwargs):
        if not self.validate_api_key() or not self.accepts({"id": model}):
            raise ValueError("Model or credential is unavailable")
        body = {"model": model, "messages": messages, "stream": False,
                "max_tokens": kwargs.get("max_tokens", 4096)}
        with self.transport.post(self.base_url.rstrip("/") + "/chat/completions",
                           headers=self.headers(), json=body, timeout=kwargs.get("timeout", 180), allow_redirects=False) as response:
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]


class LocalProvider(CompatibleProvider):
    """Ollama, llama.cpp or another explicitly configured loopback model server."""
    base_url = "http://127.0.0.1:11434/v1"
    keyless = True

    def __init__(self, api_key="", models=None, base_url=None):
        super().__init__(api_key, models, base_url)
        parsed = urlsplit(self.base_url)
        if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "::1", "localhost")
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Local models require a loopback HTTP base URL")
        self.transport = requests.Session()
        self.transport.trust_env = False


class OpenRouterFreeProvider(CompatibleProvider):
    base_url = "https://openrouter.ai/api/v1"
    environment = "OPENROUTER_API_KEY"

    def accepts(self, row):
        # Restrict requests as well as the picker: never spill Auto into paid IDs.
        return row["id"].endswith(":free") or row["id"] == "openrouter/free"

    def free_models(self):
        return self.list_models()


class GroqProvider(CompatibleProvider):
    base_url = "https://api.groq.com/openai/v1"
    environment = "GROQ_API_KEY"


class CerebrasProvider(CompatibleProvider):
    base_url = "https://api.cerebras.ai/v1"
    environment = "CEREBRAS_API_KEY"
