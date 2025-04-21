# constants.py
"""
Centralized constants and configuration for the AI CLI application.
"""

import re
from pathlib import Path
from typing import Dict, List, Pattern, Set

# --- Application Info ---
APP_NAME = "ai-assistant-multi"
APP_VERSION = "0.0.1"

# --- Configuration Paths ---
APP_DIR: Path = Path.home() / f".{APP_NAME}"
CONFIG_DIR: Path = APP_DIR / "config"
SESSION_DIR: Path = APP_DIR / "chat_sessions"
DEFAULT_CONFIG_PATH: Path = CONFIG_DIR / "config.json"

# --- AI Provider Configuration ---

# Structure defining details for each supported AI provider
PROVIDER_CONFIG: Dict[str, Dict[str, any]] = {
    "openai": {
        "name": "OpenAI",
        "required_keys": ["api_key", "model"],
        "env_var": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
        "default_temperature": 0.7,
    },
    "google": {
        "name": "Google Gemini",
        "required_keys": ["api_key", "model"],
        "env_var": "GOOGLE_API_KEY",
        "models": [
            "gemini-2.5-flash-preview-04-17",
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-latest",
            "gemini-1.0-pro",  # Often equivalent to gemini-pro
            "gemini-pro",  # Keep explicit alias
            # Older/Specific models if needed
            # "gemini-1.0-pro-001",
        ],
        "default_temperature": 0.7,
        # Default safety settings (can be overridden if needed)
        # Import HarmCategory and HarmBlockThreshold in the client file
        # "safety_settings": {
        #     HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        #     HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        #     HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        #     HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        # }
    },
    # Add configuration for other providers here
}

# --- Chat Session Settings ---
DEFAULT_CODE_THEME: str = "native"  # Default theme for Rich Markdown code blocks
MAX_UPLOAD_SIZE_KB: int = (
    50  # Max size for *each* uploaded file in interactive sessions
)
# Set of allowed file extensions for uploads (lowercase)
ALLOWED_UPLOAD_EXTENSIONS: Set[str] = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".csv",
    ".html",
    ".css",
    ".js",
    ".yaml",
    ".yml",
    ".sh",
    ".xml",
    ".log",
    ".ini",
    ".cfg",
    ".toml",
}
# Max number of filenames to show directly in the interactive prompt line
MAX_FILENAMES_IN_PROMPT: int = 3

# --- Session Management ---
# Regex to identify the UUID suffix in session filenames (e.g., _a1b2c3d4)
SESSION_ID_SUFFIX_RE: Pattern[str] = re.compile(r"_(?:[a-f0-9]{8})$")
# Max length for the user-provided part of the session name before adding suffix
MAX_SESSION_NAME_LEN: int = 50

# --- Direct Prompt Settings ---
# Allowed output formats for the 'prompt' command
OUTPUT_FORMAT_CHOICES: List[str] = ["markdown", "raw", "json"]

# --- Editor ---
# Environment variable for the external editor
EDITOR_ENV_VAR: str = "EDITOR"
# Placeholder comment written to the temp file for the /edit command
EDITOR_PLACEHOLDER_COMMENT: str = (
    "# Enter your prompt below. Save and exit the editor when done.\n"
)
