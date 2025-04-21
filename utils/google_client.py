# utils/google_client.py
"""
Concrete implementation of BaseAIClient for interacting with the Google Gemini API.
"""

import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple

# Attempt to import Google libraries, handle potential ImportError
try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    from google.generativeai.types import HarmBlockThreshold, HarmCategory

    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

    # Define dummy types if library not installed, to avoid errors elsewhere
    # This allows the CLI to run even if google client is not fully usable
    # A runtime error will occur if attempted to use without installation.
    class HarmCategory:
        HARM_CATEGORY_HARASSMENT = None
        HARM_CATEGORY_HATE_SPEECH = None
        HARM_CATEGORY_SEXUALLY_EXPLICIT = None
        HARM_CATEGORY_DANGEROUS_CONTENT = None

    class HarmBlockThreshold:
        BLOCK_MEDIUM_AND_ABOVE = None

    google_exceptions = None  # type: ignore
    genai = None  # type: ignore


from constants import PROVIDER_CONFIG  # Import for default temp

from .base_client import AIClientError, BaseAIClient

# Define safety settings using the (potentially dummy) HarmCategory types
# These might need adjustment based on specific Gemini model recommendations
DEFAULT_GOOGLE_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


class GoogleAIClient(BaseAIClient):
    """Handles non-streaming communication with the Google Gemini API."""

    def __init__(self, api_key: str, model: str, **kwargs):
        """
        Initializes the Google Gemini client.

        Args:
            api_key: Google AI API Key.
            model: Gemini model name (e.g., 'gemini-1.5-pro-latest').
            **kwargs: Additional arguments (currently unused).

        Raises:
            ImportError: If the 'google-generativeai' library is not installed.
            ValueError: If API key or model is missing.
            AIClientError: If client configuration fails.
        """
        super().__init__(api_key=api_key, model=model)

        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google AI client requires 'google-generativeai'. Please install it."
            )
        if not api_key:
            raise ValueError("Google API key cannot be empty.")
        if not model:
            raise ValueError("Google Gemini Model name cannot be empty.")

        try:
            genai.configure(api_key=self.api_key)
            # Initialize the generative model instance
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                safety_settings=DEFAULT_GOOGLE_SAFETY_SETTINGS,
            )
        except Exception as e:
            # Catch potential configuration errors (e.g., invalid key format)
            raise AIClientError(f"Failed to initialize Google Gemini client: {e}")

    def _convert_messages_to_gemini_format(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Converts the standard message history format to Gemini's required format.

        Ensures alternating 'user' and 'model' roles, which is required by the API.
        Consecutive messages from the same role might be skipped.

        Args:
            messages: List of standard message dictionaries.

        Returns:
            List of messages formatted for the Gemini API.
        """
        gemini_history = []
        last_role = None
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            gemini_role = "model" if role == "assistant" else "user"

            # Skip consecutive messages from the same role to maintain alternation
            if gemini_role == last_role:
                print(
                    f"[yellow]Warning: Skipping consecutive '{gemini_role}' message to maintain Gemini role alternation.[/]",
                    file=sys.stderr,
                )
                continue

            gemini_history.append({"role": gemini_role, "parts": [content]})
            last_role = gemini_role

        return gemini_history

    def get_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        **kwargs,
    ) -> Tuple[str, Dict[str, int]]:
        """Gets a non-streaming chat completion from the Google Gemini API."""
        if not messages:
            return "", {}

        # Convert messages, handling potential empty result or role errors
        gemini_messages = self._convert_messages_to_gemini_format(messages)
        if not gemini_messages:
            # This can happen if input messages are empty or invalid after conversion
            return "", {}  # Or raise error? Return empty seems safer.

        # Set temperature using provider default from constants if not specified
        temp_override = PROVIDER_CONFIG.get("google", {}).get("default_temperature")
        temp = temperature if temperature is not None else temp_override

        # Configure generation parameters
        generation_config = (
            genai.types.GenerationConfig(temperature=temp) if temp is not None else None
        )

        # Initialize default usage dict
        usage_dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        try:
            # Call the API
            response = self.model.generate_content(
                gemini_messages,
                generation_config=generation_config,
                # safety_settings already applied to self.model
            )

            # --- Extract Usage Metadata ---
            prompt_token_count = 0
            completion_token_count = 0
            total_token_count = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_token_count = response.usage_metadata.prompt_token_count
                completion_token_count = (
                    response.usage_metadata.candidates_token_count
                )  # Google name
                total_token_count = response.usage_metadata.total_token_count
            usage_dict = {
                "prompt_tokens": prompt_token_count,
                "completion_tokens": completion_token_count,
                "total_tokens": total_token_count,
            }
            # --- End Usage Extraction ---

            # --- Handle Response Content and Safety Blocks ---
            reply = ""
            # Check if the response was blocked or empty *before* accessing .text
            if not response.candidates:
                finish_reason_msg = "Response was empty or blocked."
                # Try to get more specific block reason
                if (
                    hasattr(response, "prompt_feedback")
                    and response.prompt_feedback.block_reason
                ):
                    finish_reason_msg = f"Response blocked due to: {response.prompt_feedback.block_reason.name}"
                raise AIClientError(finish_reason_msg)
            else:
                try:
                    # Accessing .text can raise ValueError if blocked internally
                    reply = response.text
                except ValueError as ve:
                    # Handle case where .text access fails despite candidates existing
                    finish_reason_msg = (
                        f"Response blocked (ValueError accessing .text): {ve}"
                    )
                    if (
                        hasattr(response, "prompt_feedback")
                        and response.prompt_feedback.block_reason
                    ):
                        finish_reason_msg = f"Response blocked due to: {response.prompt_feedback.block_reason.name}"
                    raise AIClientError(finish_reason_msg)
            # --- End Content Handling ---

            return reply, usage_dict

        # --- Specific Error Handling ---
        except google_exceptions.PermissionDenied as e:
            raise AIClientError(f"Google API Permission Denied (Check API Key): {e}")
        except google_exceptions.ResourceExhausted as e:
            raise AIClientError(f"Google API Resource Exhausted (Rate Limit?): {e}")
        except google_exceptions.InvalidArgument as e:
            # Check for common role alternation error message
            if (
                "please ensure that multiturn requests alternate between user and model"
                in str(e).lower()
            ):
                raise AIClientError(
                    f"Google API Invalid Argument: History must alternate roles. Check prompt conversion. Details: {e}"
                )
            else:
                raise AIClientError(f"Google API Invalid Argument: {e}")
        except (
            google_exceptions.GoogleAPIError
        ) as e:  # Catch other specific Google API errors
            raise AIClientError(f"Google API Error: {e}")
        except AIClientError:  # Re-raise safety block errors from above
            raise
        except Exception as e:  # Catch other unexpected errors
            # Check for safety block messages in generic exceptions too
            if (
                hasattr(e, "message")
                and "response was blocked by safety settings"
                in str(getattr(e, "message", "")).lower()
            ):
                raise AIClientError(
                    f"Google API: Response blocked by safety settings. Details: {e}"
                )
            # Log unexpected error details
            traceback.print_exc(file=sys.stderr)
            raise AIClientError(
                f"An unexpected error occurred during Google API call: {e}"
            )
