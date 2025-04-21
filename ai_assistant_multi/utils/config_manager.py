# utils/config_manager.py
"""
Manages loading, saving, and validation of the application's configuration.

Handles the multi-provider structure, default provider settings, and ensures
required keys (API key, model) are present for configured providers.
"""

import json
import os  # Import os for getenv
import traceback  # Import for unexpected errors during load/save
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich import print as rich_print

# Import constants from the central file
from ..constants import CONFIG_DIR  # Import directory path too
from ..constants import DEFAULT_CONFIG_PATH, PROVIDER_CONFIG


class ConfigError(Exception):
    """Custom exception for configuration-related errors."""

    pass


class ConfigManager:
    """Handles loading, saving, and access to multi-provider configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initializes the ConfigManager.

        Args:
            config_path: Optional path to the configuration file.
                         Defaults to DEFAULT_CONFIG_PATH from constants.
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        # In-memory cache of the loaded config (cleared on re-init)
        self._config: Optional[Dict[str, Any]] = None
        self._ensure_config_dir_exists()

    def _ensure_config_dir_exists(self):
        """Ensures the configuration directory exists, creating it if necessary."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Handle potential permission errors during directory creation
            raise ConfigError(f"Could not create config directory {CONFIG_DIR}: {e}")

    def load(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Loads the configuration from the JSON file.

        Uses an in-memory cache unless force_reload is True.
        Handles file not found, empty file, and JSON decoding errors gracefully
        by returning a default structure.

        Args:
            force_reload: If True, bypasses the cache and reads from disk.

        Returns:
            The configuration dictionary.
        """
        # Use cache if available and not forcing reload
        if self._config is not None and not force_reload:
            return self._config

        config_data: Dict[str, Any] = {}  # Default empty structure

        if self.config_path.exists():
            try:
                content = self.config_path.read_text(encoding="utf-8")
                if content.strip():  # File has content
                    loaded_json = json.loads(content)
                    # Ensure the loaded content is a dictionary
                    if isinstance(loaded_json, dict):
                        config_data = loaded_json
                    else:
                        # Log error if config file is not a dictionary
                        rich_print(
                            f"[bold red]Error: Config file ({self.config_path}) does not contain a valid JSON object. Using default.[/]"
                        )
                        # Optionally backup the invalid file here
                # If file exists but is empty, config_data remains {}
            except json.JSONDecodeError as e:
                rich_print(
                    f"[bold yellow]Warning: Error decoding config file ({self.config_path}): {e}. Using default.[/]"
                )
                # Optionally backup the invalid file here
            except IOError as e:
                rich_print(
                    f"[bold yellow]Warning: Could not read config file ({self.config_path}): {e}. Using default.[/]"
                )
            except Exception as e:
                # Catch unexpected errors during load
                rich_print(
                    f"[bold red]Unexpected error loading config ({self.config_path}): {e}. Using default.[/]"
                )
                traceback.print_exc(file=sys.stderr)  # Use sys import

        # Ensure the basic structure ('default_provider', 'providers') exists
        config_data.setdefault("default_provider", None)
        config_data.setdefault("providers", {})

        # Update the cache
        self._config = config_data
        return self._config

    def save(self, data: Dict[str, Any]):
        """
        Saves the provided configuration data structure to the JSON file.

        Overwrites the existing file. Ensures the parent directory exists.

        Args:
            data: The configuration dictionary to save.

        Raises:
            ConfigError: If saving fails due to IO or type errors.
        """
        self._ensure_config_dir_exists()  # Ensure directory exists before writing
        try:
            # Ensure basic structure keys exist before saving
            data.setdefault("default_provider", None)
            data.setdefault("providers", {})
            # Write data with indentation for readability
            self.config_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
            # Update the cache with the saved data
            self._config = data
            # Optionally print success message (maybe only in setup commands?)
            # rich_print(f"[green]Configuration saved to {self.config_path}[/]")
        except IOError as e:
            raise ConfigError(
                f"Error saving configuration file to {self.config_path}: {e}"
            )
        except TypeError as e:
            # This might happen if data contains non-serializable types
            raise ConfigError(f"Invalid data structure for configuration: {e}")
        except Exception as e:
            # Catch unexpected save errors
            raise ConfigError(f"Unexpected error saving configuration: {e}")

    def get_default_provider(self) -> Optional[str]:
        """Returns the key of the configured default provider, or None."""
        config = self.load()
        return config.get("default_provider")

    def get_provider_config(self, provider_key: str) -> Optional[Dict[str, Any]]:
        """
        Returns the configuration dictionary for a specific provider key.

        Args:
            provider_key: The key of the provider (e.g., 'openai').

        Returns:
            The provider's configuration dict, or None if not found.
        """
        config = self.load()
        # Normalize key just in case
        return config.get("providers", {}).get(provider_key.lower())

    def get_available_providers(self) -> List[str]:
        """Returns a list of provider keys present in the configuration file."""
        config = self.load()
        return list(config.get("providers", {}).keys())

    def check_config_exists(self) -> bool:
        """Checks if the config file exists and is not empty."""
        try:
            return self.config_path.exists() and self.config_path.stat().st_size > 0
        except OSError:
            return False  # Cannot stat file (e.g. permissions)

    def get_api_key(self, provider_key: str) -> Optional[str]:
        """
        Gets the API key for a provider, checking config and environment variables.

        Args:
            provider_key: The key of the provider (e.g., 'openai').

        Returns:
            The API key string, or None if not found.
        """
        provider_key = provider_key.lower()
        provider_info = PROVIDER_CONFIG.get(provider_key, {})
        env_var_name = provider_info.get("env_var")

        # 1. Check Environment Variable
        if env_var_name:
            key_from_env = os.getenv(env_var_name)
            if key_from_env:
                return key_from_env

        # 2. Check Configuration File
        provider_settings = self.get_provider_config(provider_key)
        if provider_settings:
            key_from_config = provider_settings.get("api_key")
            if key_from_config:
                return key_from_config

        # Not found in either location
        return None
