"""WusRouter OpenAI-compatible API with public live model discovery."""
import os
import requests
from providers.ourfree.ourfree_provider import OurFreeModelProvider

DEFAULT_BASE_URL = "https://wusrouter.com/v1"
SIGNUP_URL = "https://wusrouter.com/"


class WusRouterProvider(OurFreeModelProvider):
    """Discover publicly; use an account API key for chat."""

    signup_url = SIGNUP_URL

    def __init__(self, api_key="", models=None, base_url=None):
        super().__init__(api_key or os.environ.get("WUSROUTER_API_KEY", ""), models,
                         base_url or DEFAULT_BASE_URL)
        self.default_models = []

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key.strip()}"
        return headers

    def list_models(self):
        try:
            response = requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=10)
            if response.status_code == 200:
                payload = response.json()
                rows = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(rows, list):
                    return list(dict.fromkeys(row["id"] for row in rows
                        if isinstance(row, dict) and isinstance(row.get("id"), str)
                        and row["id"].strip()))
        except (requests.RequestException, ValueError):
            pass
        return list(self.models)
