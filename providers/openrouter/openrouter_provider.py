"""
OpenRouter provider for codelaboon.

Implements the BaseProvider interface for OpenRouter models (aggregator of multiple providers).
"""

import os
import requests
from typing import List, Dict, Any
from providers.base import BaseProvider


class OpenRouterProvider(BaseProvider):
    """Provider for OpenRouter models (aggregator)."""

    decision_protocol = "systemone"
    
    def __init__(self, api_key: str, models: List[str] = None):
        """
        Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key
            models: Optional list of models (defaults to available models)
        """
        super().__init__(api_key, models)
        self.base_url = "https://openrouter.ai/api/v1"
        self.default_models = [
            "openai/gpt-3.5-turbo",
            "openai/gpt-4",
            "anthropic/claude-2",
            "google/palm-2-chat-bison",
            "meta-llama/llama-2-70b-chat"
        ]

    def decision_headers(self):
        """Add OpenRouter attribution headers to decision requests."""
        headers = super().decision_headers()
        headers["HTTP-Referer"] = "https://github.com/zGabrielR1/codelaboon"
        headers["X-Title"] = "codelaboon"
        return headers
    
    def list_models(self) -> List[str]:
        """
        List available OpenRouter models.
        
        Returns:
            List of available model names
        """
        if self.models:
            return self.models
        
        # Return default models
        return self.default_models.copy()
    
    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to OpenRouter.
        
        Args:
            model: Model name to use
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            String response from the model
        """
        if not self.validate_api_key():
            raise ValueError("Invalid or missing API key")
        
        # Prepare request headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://codelaboon.example.com",  # Replace with actual site
            "X-Title": "codelaboon"  # Replace with actual title
        }
        
        # Prepare request data
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
            json=data
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
        Parse OpenRouter API response.
        
        Args:
            response_data: Raw response data from OpenRouter API
            
        Returns:
            Parsed string response
        """
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError("Invalid response format: no choices")
        
        choice = response_data["choices"][0]
        if "message" not in choice or "content" not in choice["message"]:
            raise ValueError("Invalid response format: no message content")
        
        return choice["message"]["content"]