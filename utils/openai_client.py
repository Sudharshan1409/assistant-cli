# utils/openai_client.py
"""
Concrete implementation of BaseAIClient for interacting with the OpenAI API.
"""
import sys
import traceback
from typing import Dict, List, Optional, Tuple

# Attempt to import OpenAI library, handle potential ImportError
try:
    from openai import OpenAI, OpenAIError

    OPENAI_API_AVAILABLE = True
except ImportError:
    OPENAI_API_AVAILABLE = False

    # Define dummy types/classes if library not installed
    # Allows CLI to load but will raise error if OpenAIClient is used.
    class OpenAI:
        pass

    class OpenAIError(Exception):
        pass


from constants import PROVIDER_CONFIG  # Import for default temp

from .base_client import AIClientError, BaseAIClient


class OpenAIClient(BaseAIClient):
    """Handles non-streaming communication with the OpenAI API."""

    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initializes the OpenAI client.

        Args:
            api_key: OpenAI API Key.
            model: OpenAI model name (e.g., 'gpt-4o').
            **kwargs: Additional arguments (e.g., base_url for proxies).

        Raises:
            ImportError: If the 'openai' library is not installed.
            ValueError: If API key or model is missing.
            AIClientError: If client initialization fails.
        """
        super().__init__(api_key=api_key, model=model)

        if not OPENAI_API_AVAILABLE:
            raise ImportError(
                "OpenAI client requires the 'openai' library. Please install it."
            )
        if not api_key:
            raise ValueError("OpenAI API key cannot be empty.")
        if not model:
            raise ValueError("OpenAI Model name cannot be empty.")

        try:
            # Initialize the OpenAI client instance
            # Pass through other kwargs like base_url, timeout
            self.client = OpenAI(api_key=self.api_key, **kwargs)
        except Exception as e:
            raise AIClientError(f"Failed to initialize OpenAI client: {e}")

    def get_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs,
    ) -> Tuple[str, Dict[str, int]]:
        """Gets a non-streaming chat completion from the OpenAI API."""
        if not messages:
            return "", {}

        # Set temperature using provider default from constants if not specified
        temp_override = PROVIDER_CONFIG.get("openai", {}).get("default_temperature")
        temp = temperature if temperature is not None else temp_override

        # Combine passed kwargs with default temperature
        final_kwargs = {"temperature": temp, **kwargs} if temp is not None else kwargs

        try:
            # Call the chat completions endpoint
            response = self.client.chat.completions.create(
                model=self.model_name, messages=messages, **final_kwargs
            )

            # --- Extract Response and Usage ---
            reply = ""
            # Ensure response structure is as expected before accessing attributes
            if response.choices and response.choices[0].message:
                reply = response.choices[0].message.content or ""

            usage_data = response.usage
            usage_dict = {
                "prompt_tokens": usage_data.prompt_tokens if usage_data else 0,
                "completion_tokens": usage_data.completion_tokens if usage_data else 0,
                "total_tokens": usage_data.total_tokens if usage_data else 0,
            }
            # --- End Extraction ---

            return reply, usage_dict

        # --- Error Handling ---
        except OpenAIError as e:
            # Attempt to extract more detailed error message from OpenAIError
            error_detail = str(e)
            if hasattr(e, "body") and isinstance(e.body, dict) and "message" in e.body:
                error_detail = f"{e.body['message']} (Code: {getattr(e, 'code', 'N/A')}, Type: {getattr(e, 'type', 'N/A')})"
            elif hasattr(e, "message") and e.message:
                error_detail = e.message
            raise AIClientError(f"OpenAI API error: {error_detail}")
        except Exception as e:
            # Catch other unexpected errors during API call
            traceback.print_exc(file=sys.stderr)
            raise AIClientError(
                f"An unexpected error occurred during OpenAI API call: {e}"
            )
