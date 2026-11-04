"""
Base provider interface for codelaboon.

All providers must implement this interface to work with the codelaboon harness.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseProvider(ABC):
    """Abstract base class for all AI model providers."""
    
    def __init__(self, api_key: str, models: List[str] = None):
        """
        Initialize provider with API key and optional model list.
        
        Args:
            api_key: API key for the provider
            models: Optional list of models to use (empty list = auto-discover)
        """
        self.api_key = api_key
        self.models = models or []
        self._validated = False
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """
        List available models for this provider.
        
        Returns:
            List of model names available
        """
        pass
    
    @abstractmethod
    def chat(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Send a chat completion request.
        
        Args:
            model: Model name to use
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            String response from the model
        """
        pass
    
    def validate_api_key(self) -> bool:
        """
        Validate the API key and return authentication status.
        
        Returns:
            True if API key is valid, False otherwise
        """
        # Default implementation - subclasses should override
        # for provider-specific validation
        return bool(self.api_key and len(self.api_key.strip()) > 0)
    
    def _make_request(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Make an API request to the provider.
        
        Args:
            model: Model name
            messages: Message list
            **kwargs: Additional parameters
            
        Returns:
            Response string
        """
        # This is a placeholder - each provider should implement its own request logic
        # based on its specific API requirements
        raise NotImplementedError("Subclasses must implement _make_request")
    
    def _parse_response(self, response_data: Any) -> str:
        """
        Parse provider-specific response format into a string.
        
        Args:
            response_data: Raw response data from API
            
        Returns:
            Parsed string response
        """
        # This is a placeholder - each provider should implement its own parsing logic
        # based on its specific response format
        raise NotImplementedError("Subclasses must implement _parse_response")