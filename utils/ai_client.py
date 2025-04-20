# utils/ai_client.py
from typing import Dict, List, Optional

from openai import OpenAI, OpenAIError


class AIClientError(Exception):
    """Custom exception for AI client errors."""

    pass


class AIClient:
    """Handles communication with the OpenAI API."""

    DEFAULT_TEMPERATURE = 0.7

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        if not model:
            raise ValueError("Model name cannot be empty.")

        self.api_key = api_key
        self.model = model
        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as e:  # Catch potential init errors
            raise AIClientError(f"Failed to initialize OpenAI client: {e}")

    def get_completion(
        self, messages: List[Dict[str, str]], temperature: Optional[float] = None
    ) -> str:
        """Gets a chat completion from the OpenAI API."""
        if not messages:
            # Decide behavior: return empty, raise error?
            return ""  # Or raise ValueError("Cannot get completion for empty message list.")

        temp = temperature if temperature is not None else self.DEFAULT_TEMPERATURE

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temp,
            )
            reply = response.choices[0].message.content
            return reply if reply else ""  # Ensure we return string
        except OpenAIError as e:
            # More specific error handling can be added here (e.g., auth, rate limit)
            raise AIClientError(f"OpenAI API error: {e}")
        except Exception as e:
            # Catch other potential issues
            raise AIClientError(f"An unexpected error occurred during API call: {e}")
