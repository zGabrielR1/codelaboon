"""
Base provider interface for codelaboon.

All providers must implement this interface to work with the codelaboon harness.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

import requests


class BaseProvider(ABC):
    """Abstract base class for all AI model providers."""

    # "openai" or "systemone"; None means the provider has no decision route.
    decision_protocol: Optional[str] = None

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

    def supports_decisions(self) -> bool:
        """Whether this provider exposes a typed decision route."""
        return self.decision_protocol in ("openai", "systemone")

    def decision_headers(self) -> Dict[str, str]:
        """Headers used for decision requests. Providers may extend this."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def decision(
        self,
        model: str,
        input_text: str,
        questions: List[Any],
        **kwargs,
    ) -> List[Any]:
        """Ask typed decision questions about ``input_text``.

        Args:
            model: Decision model name.
            input_text: Text input to evaluate.
            questions: Typed questions from :mod:`codelaboon.decision`.
            **kwargs: ``timeout`` in seconds (default 60).

        Returns:
            Answers in the same order as ``questions``.
        """
        if not self.supports_decisions():
            raise NotImplementedError(
                f"{type(self).__name__} does not support decision models"
            )
        if not self.validate_api_key():
            raise ValueError("Invalid or missing API key")

        from codelaboon.decision import build_body, parse_response

        path = "decisions" if self.decision_protocol == "openai" else "systemone"
        url = f"{self.base_url.rstrip('/')}/{path}"
        body = build_body(self.decision_protocol, model, input_text, questions)
        response = requests.post(
            url,
            headers=self.decision_headers(),
            json=body,
            timeout=kwargs.get("timeout", 60),
        )
        if response.status_code != 200:
            raise Exception(
                f"Decision request failed: {response.status_code} - {response.text}"
            )
        return parse_response(self.decision_protocol, response.json(), questions)
    
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