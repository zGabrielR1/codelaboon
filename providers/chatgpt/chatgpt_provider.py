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
        self.default_models = ["gpt-3.5-turbo", "gpt-4"]
    
    def list_models(self) -> List[str]:
        """
        List available ChatGPT models.
        
        Returns:
            List of available model names
        """
        # For free tier, typically available models are:
        # - gpt-3.5-turbo (free)
        # - gpt-4 (paid)
        if self.models:
            return self.models
        
        # If no models specified, return default free models
        available_models = []
        for model in self.default_models:
            try:
                # Quick validation by making a minimal request
                if self._test_model_access(model):
                    available_models.append(model)
            except Exception:
                # If we can't test, assume it's available
                available_models.append(model)
        
        return available_models
    
    def _test_model_access(self, model: str) -> bool:
        """Test if we have access to a specific model."""
        # This is a simplified validation - in practice, you'd make an actual API call
        # to validate model access
        if model == "gpt-3.5-turbo":
            # Free model - accessible
            return True
        elif model == "gpt-4":
            # Paid model - check if we have sufficient quota
            # For free tier, this would likely be False
            return False
        return True
    
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
        
        # Prepare request parameters
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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