"""
NVIDIA Nemotron provider for codelaboon.

Implements the BaseProvider interface for NVIDIA's Nemotron models.
"""

import os
import requests
import json
from typing import List, Dict, Any
from providers.base import BaseProvider


class NVIDIAProvider(BaseProvider):
    """Provider for NVIDIA Nemotron models."""
    
    def __init__(self, api_key: str, models: List[str] = None):
        """
        Initialize NVIDIA provider.
        
        Args:
            api_key: NVIDIA API key
            models: Optional list of models (defaults to available models)
        """
        super().__init__(api_key, models)
        self.base_url = "https://integrate.api.nvidia.com/v1"
        self.default_models = ["nemotron-3", "nemotron-4"]
    
    def list_models(self) -> List[str]:
        """
        List available NVIDIA Nemotron models.
        
        Returns:
            List of available model names
        """
        if self.models:
            return self.models
        
        # Default to Nemotron models
        return self.default_models.copy()
    
    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request to NVIDIA Nemotron.
        
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
            "Content-Type": "application/json"
        }
        
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
        Parse NVIDIA Nemotron API response.
        
        Args:
            response_data: Raw response data from NVIDIA API
            
        Returns:
            Parsed string response
        """
        if "choices" not in response_data or not response_data["choices"]:
            raise ValueError("Invalid response format: no choices")
        
        choice = response_data["choices"][0]
        if "message" not in choice or "content" not in choice["message"]:
            raise ValueError("Invalid response format: no message content")
        
        return choice["message"]["content"]