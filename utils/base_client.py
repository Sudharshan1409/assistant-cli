# utils/base_client.py
"""
Defines the abstract base class and common error type for AI clients.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple


class BaseAIClient(ABC):
    """Abstract base class for different AI client implementations."""

    @abstractmethod
    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initializes the client.

        Args:
            api_key: The API key for the AI service.
            model: The specific model identifier to use.
            **kwargs: Additional provider-specific settings.
        """
        self.api_key = api_key
        self.model_name = model
        # Subclasses should perform validation and setup (e.g., SDK client init)

    @abstractmethod
    def get_completion(
        self, messages: List[Dict[str, str]], **kwargs
    ) -> Tuple[str, Dict[str, int]]:
        """
        Sends messages to the AI model and gets a complete response.

        Args:
            messages: A list of message dictionaries, conforming to the
                      provider's expected format (typically {'role': str, 'content': str}).
            **kwargs: Additional provider-specific parameters (e.g., temperature).

        Returns:
            A tuple containing:
                - The AI's response content as a string.
                - A dictionary with token usage information (keys like
                  'prompt_tokens', 'completion_tokens', 'total_tokens').
                  Return empty dict or zeros if usage is unavailable.

        Raises:
            AIClientError: If an API interaction error occurs.
            ValueError: If input parameters are invalid.
        """
        pass  # Subclasses must implement this


class AIClientError(Exception):
    """Custom exception raised for errors during AI client interactions."""

    pass
