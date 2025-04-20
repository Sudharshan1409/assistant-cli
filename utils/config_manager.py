# utils/config_manager.py
import json
from pathlib import Path
from typing import Any, Dict, Optional

import typer  # Keep for typer.Exit if preferred, or use custom exceptions
from rich import print


class ConfigError(Exception):
    """Custom exception for configuration errors."""

    pass


class ConfigManager:
    """Handles loading, saving, and validation of application configuration."""

    DEFAULT_CONFIG_PATH = Path.home() / ".ai-cli/config/config.json"
    REQUIRED_KEYS = ["openai_api_key", "model"]

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Optional[Dict[str, Any]] = None
        self._ensure_config_dir_exists()

    def _ensure_config_dir_exists(self):
        """Ensures the configuration directory exists."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        """Loads configuration from the file."""
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            self._config = {}
            return self._config

        try:
            with self.config_path.open("r") as f:
                self._config = json.load(f)
                return self._config
        except (json.JSONDecodeError, IOError) as e:
            raise ConfigError(f"Error loading configuration file: {e}")

    def save(self, data: Dict[str, Any]):
        """Saves configuration data to the file."""
        try:
            with self.config_path.open("w") as f:
                json.dump(data, f, indent=4)
            self._config = data  # Update cached config
            print(
                f"[bold green]✅ Configuration saved successfully to {self.config_path}[/bold green]"
            )
        except IOError as e:
            raise ConfigError(f"Error saving configuration file: {e}")

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Gets a specific configuration value."""
        config = self.load()
        return config.get(key, default)

    def get_required_config(self) -> Dict[str, Any]:
        """Loads config and validates required keys."""
        config = self.load()
        missing_keys = [key for key in self.REQUIRED_KEYS if not config.get(key)]
        if missing_keys:
            keys_str = ", ".join(missing_keys)
            print(
                f"[bold red]❌ Configuration missing required keys: {keys_str}.[/bold red]"
            )
            print("[bold yellow]💡 Please run the 'setup' command first.[/bold yellow]")
            raise typer.Exit(code=1)  # Or raise ConfigError("Missing required keys...")
        return config

    def check_config_exists(self) -> bool:
        """Checks if the config file exists and is non-empty."""
        return self.config_path.exists() and self.config_path.stat().st_size > 0
