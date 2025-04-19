import json
from pathlib import Path

import typer

CONFIG_FILE = Path.home() / ".ai-cli/config/config.json"


def save_config(data):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w") as f:
        json.dump(data, f, indent=4)


def load_config():
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("r") as f:
        return json.load(f)


# Helper function for checking API key and model configuration
def check_config(config):
    if not config.get("openai_api_key") or not config.get("model"):
        print(
            "[bold red]❌ Please run `setup` first to configure API key and model.[/bold red]"
        )
        raise typer.Exit()
