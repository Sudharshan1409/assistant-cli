# commands/setup_cmd.py
import os
import traceback
from typing import Dict, Optional

import click
import questionary
import typer
from rich import print
from rich.markup import escape

from utils.config_manager import ConfigError, ConfigManager

# Model choices remain the same
MODEL_CHOICES = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"]

app = typer.Typer(help="Configure application settings.")

# Instantiate the manager
config_manager = ConfigManager()


# --- MODIFIED Helper function to prompt for key ---
def _prompt_for_api_key(current_config: Dict) -> str:
    """Prompts user for API key, using config value as default but not showing it."""
    existing_key = current_config.get("openai_api_key", None)
    prompt_message = "Enter your OpenAI API key"
    if existing_key:
        # If a key exists, hint that pressing Enter uses the current one
        prompt_message += " (press Enter to keep current)"

    new_key = typer.prompt(
        prompt_message,
        default=existing_key,
        hide_input=True,
        show_default=False,  # <-- Add this line
    )
    # If user just presses Enter and a default existed, new_key will be the default.
    # If user types something, new_key will be the typed value.
    # If user presses Enter and no default existed, new_key will be an empty string.

    if (
        not new_key
    ):  # Check if the result is empty (only possible if no default and user hit Enter)
        print("[bold red]❌ API key cannot be empty.[/bold red]")
        raise typer.Exit(code=1)
    return new_key


# --- END MODIFIED Helper ---


@app.command("configure")
def configure_settings(
    openai_api_key: Optional[str] = typer.Option(
        None,
        "--openai-api-key",
        "-k",
        help="Your OpenAI API key (leave empty for prompt)",
        envvar="OPENAI_API_KEY",
        show_default=False,
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (leave empty for prompt)",
        show_default=False,
    ),
):
    """
    Configure your AI Assistant credentials and settings interactively or via options.
    """
    try:
        current_config = config_manager.load()
        final_api_key = openai_api_key
        key_source = "Unknown"

        # --- Determine Key Source and Ask for Confirmation ---
        if final_api_key:
            env_var_value = os.getenv("OPENAI_API_KEY")
            if env_var_value and env_var_value == final_api_key:
                key_source = "Environment Variable (OPENAI_API_KEY)"
            else:
                key_source = "Command-Line Option (--openai-api-key / -k)"

            print(f"[dim]Found OpenAI API key from: {key_source}[/dim]")
            masked_found_key = (
                f"{final_api_key[:4]}...{final_api_key[-4:]}"
                if len(final_api_key) > 8
                else "<key hidden>"
            )

            use_found_key = questionary.confirm(
                f"Use this key ({masked_found_key})?", default=True
            ).ask()

            if use_found_key is None:
                print("\nConfiguration cancelled.")
                raise typer.Exit()

            if not use_found_key:
                print("[dim]Enter the API key you want to use instead:[/dim]")
                # Pass current_config so it can potentially show "press Enter" hint
                final_api_key = _prompt_for_api_key(current_config)
                key_source = "User Prompt (Override)"
            # else: Keep using the final_api_key from option/env

        else:
            print(
                "[dim]OpenAI API key not found in options or environment variable.[/dim]"
            )
            final_api_key = _prompt_for_api_key(current_config)
            key_source = "User Prompt"

        # --- Model Selection ---
        selected_model = model
        model_source = (
            "Command-Line Option (--model / -m)" if selected_model else "User Prompt"
        )

        if not selected_model:
            print("\n[dim]Select the AI model you want to use:[/dim]")
            selected_model = questionary.select(
                "Choose model:",
                choices=MODEL_CHOICES,
                default=current_config.get("model", None),
                instruction="(Use arrow keys, Enter to select)",
            ).ask()

            if selected_model is None:
                print("Model selection cancelled.")
                raise typer.Exit()
            model_source = "User Prompt"

        print(f"[dim]Using model from: {model_source}[/dim]")

        if selected_model not in MODEL_CHOICES:
            print(
                f"[bold red]❌ Invalid model '{selected_model}'. Choose from: {', '.join(MODEL_CHOICES)}[/bold red]"
            )
            raise typer.Exit(code=1)

        # --- Save Configuration ---
        config_data = {"openai_api_key": final_api_key, "model": selected_model}

        config_manager.save(config_data)
        masked_saved_key = (
            f"{final_api_key[:4]}...{final_api_key[-4:]}"
            if len(final_api_key) > 8
            else "<key hidden>"
        )
        print("\n[bold]Configuration Saved:[/bold]")
        print(f"  API Key Source: {key_source}")
        print(f"  API Key (Saved): [sensitive]{masked_saved_key}[/sensitive]")
        print(f"  Model Source: {model_source}")
        print(f"  Model (Saved): [cyan]{selected_model}[/cyan]")

    except ConfigError as e:
        print(f"[bold red]❌ Configuration Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        print("\nConfiguration cancelled.")
        raise typer.Exit()
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        print(
            f"[bold red]❌ Unexpected error during configuration: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)


# --- view command remains the same ---
@app.command("view")
def view_config():
    """View the current configuration."""
    try:
        if not config_manager.check_config_exists():
            print(
                "[yellow]⚠️ No configuration file found. Run 'setup configure' first.[/yellow]"
            )
            raise typer.Exit()

        config = config_manager.load()
        print("[bold blue]Current Configuration:[/bold blue]")
        api_key = config.get("openai_api_key", "Not Set")
        masked_key = (
            f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "<key hidden>"
        )
        print(f"  API Key: [sensitive]{masked_key}[/sensitive]")
        print(f"  Model: {config.get('model', 'Not Set')}")
        print(f"  Config File: {config_manager.config_path}")

    except ConfigError as e:
        print(f"[bold red]❌ Error loading configuration: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        print(
            f"[bold red]❌ Unexpected error viewing config: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)
