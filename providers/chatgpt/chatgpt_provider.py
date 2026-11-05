"""
ChatGPT provider for codelaboon.

Implements the BaseProvider interface for OpenAI's ChatGPT models.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from providers.base import BaseProvider


class ChatGPTProvider(BaseProvider):
    """Provider for OpenAI's ChatGPT models."""

    decision_protocol = "openai"
    
    def __init__(self, api_key: str, models: List[str] = None, base_url: Optional[str] = None):
        """
        Initialize ChatGPT provider.
        
        Args:
            api_key: OpenAI API key
            models: Optional list of models (defaults to available free models)
            base_url: Optional base URL override
        """
        self.base_url = "https://api.openai.com/v1"
        super().__init__(api_key, models, base_url)
        self.model_names = {}

    def validate_api_key(self) -> bool:
        from codelaboon.chatgpt_auth import read_session
        return bool(self.api_key.strip() or os.environ.get("OPENAI_API_KEY", "").strip() or read_session())

    def _credential(self):
        from codelaboon.chatgpt_auth import access_token
        # Explicit API configuration takes precedence over a saved subscription.
        key = self.api_key.strip() or os.environ.get("OPENAI_API_KEY", "").strip()
        if key:
            return key, False
        if self.base_url.rstrip("/") != "https://api.openai.com/v1":
            raise ValueError("ChatGPT sign-in tokens can only be sent to OpenAI.")
        return access_token(), True

    def list_models(self) -> List[str]:
        key, subscription = self._credential()
        if not key:
            return []
        try:
            response = requests.get(f"{self.base_url.rstrip('/')}/models", headers={"Authorization": f"Bearer {key}"}, timeout=20)
            if response.status_code != 200:
                raise ValueError("Model discovery failed. Check your OpenAI credentials and retry.")
            data = response.json()
            if subscription:
                rows = data.get("models")
                if not isinstance(rows, list):
                    raise ValueError("Invalid ChatGPT model catalogue")
                rows = [r for r in rows if isinstance(r, dict) and r.get("visibility") == "list" and isinstance(r.get("slug"), str)]
                self.model_names = {r["slug"]: r.get("display_name", r["slug"]) for r in rows}
                return list(self.model_names)
            rows = data.get("data")
            if not isinstance(rows, list):
                raise ValueError("Invalid OpenAI model catalogue")
            return sorted({r["id"] for r in rows if isinstance(r,dict) and isinstance(r.get("id"),str) and (r["id"].startswith(("gpt-", "chatgpt-", "o1", "o3", "o4"))) and not any(part in r["id"] for part in ("image", "audio", "realtime", "transcribe", "tts", "search"))}, reverse=True)
        except requests.RequestException as error:
            raise ValueError("Cannot reach OpenAI model discovery. Check your connection and retry.") from error

    def _subscription_chat(self, token, model, messages):
        response = requests.post("https://api.openai.com/v1/responses", headers={"Authorization":f"Bearer {token}"}, json={"model":model,"input":messages,"store":False,"stream":True}, stream=True, timeout=(15,180))
        try:
            if response.status_code != 200:
                raise ValueError(f"ChatGPT request failed (HTTP {response.status_code}). Check plan access and limits.")
            chunks = []
            for line in response.iter_lines():
                if not line or not line.startswith(b"data:"):
                    continue
                raw = line[5:].strip()
                if raw == b"[DONE]":
                    continue
                import json
                event = json.loads(raw)
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    chunks.append(event.get("delta", ""))
                elif kind == "response.completed":
                    return "".join(chunks)
                elif kind in ("response.failed", "response.incomplete", "error"):
                    raise ValueError("ChatGPT did not complete the response. Check plan limits and retry.")
            raise ValueError("ChatGPT connection ended before completion. Please retry.")
        finally:
            response.close()

    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to ChatGPT.
        
        Args:
            model: Model name to use
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            String response from the model
        """
        if not self.validate_api_key():
            raise ValueError("Invalid or missing API key")
        
        credential, subscription = self._credential()
        if subscription:
            return self._subscription_chat(credential, model, messages)

        # Prepare request parameters
        headers = {
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 1000),
            "top_p": kwargs.get("top_p", 1.0),
            "frequency_penalty": kwargs.get("frequency_penalty", 0.0),
            "presence_penalty": kwargs.get("presence_penalty", 0.0)
        }
        
        # Make API request
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=(15, 180),
        )
        
        if response.status_code != 200:
            raise ValueError(f"OpenAI request failed (HTTP {response.status_code}). Check credentials, model access and limits.")
        
        # Parse response
        response_data = response.json()
        return self._parse_response(response_data)
    
    def _make_request(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """Make API request (alias for chat method)."""
        return self.chat(model, messages, **kwargs)
    
    def _parse_response(self, response_data: Any) -> str:
        """
        Parse ChatGPT API response.
        
        Args:
            response_data: Raw response data from OpenAI API
            
        Returns:
            Parsed string response
        """
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError("Invalid response format: no choices")
        
        choice = response_data["choices"][0]
        if "message" not in choice or "content" not in choice["message"]:
            raise ValueError("Invalid response format: no message content")
        
        return choice["message"]["content"]