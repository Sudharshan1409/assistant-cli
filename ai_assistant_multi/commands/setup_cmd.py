# commands/setup_cmd.py
"""
Handles the 'setup' subcommands for configuring the AI CLI application.

Allows users to configure provider API keys, default models, and set the
global default provider. Also provides a command to view the current config.
"""

import os
import traceback
from typing import Optional

import click  # Used indirectly by typer for Exit exceptions
import questionary
import typer
from rich import print as rich_print
from rich.markup import escape

# Import provider definitions from the central constants file
from ..constants import PROVIDER_CONFIG

# Import configuration handling logic and error type
from ..utils.config_manager import ConfigError, ConfigManager

# Create a Typer app for the 'setup' subcommands
app = typer.Typer(help="Configure application settings for AI providers.")

# Instantiate the config manager (uses default path from constants)
config_manager = ConfigManager()


def _prompt_for_api_key(
    provider_display_name: str, env_var_name: Optional[str], current_key: Optional[str]
) -> str:
    """
    Securely prompts the user for an API key for a given provider.

    Checks environment variables and current configuration for existing keys,
    using them as defaults but hiding the actual key value.

    Args:
        provider_display_name: User-friendly name of the provider (e.g., "OpenAI").
        env_var_name: Name of the environment variable to check (e.g., "OPENAI_API_KEY").
        current_key: The currently configured key (if any).

    Returns:
        The entered API key.

    Raises:
        typer.Exit: If the user provides an empty key.
    """
    key_from_env = os.getenv(env_var_name) if env_var_name else None
    # Use env var if present, otherwise use the currently configured key
    default_key_value = key_from_env or current_key
    # Determine source for prompt clarity, but don't reveal the key
    key_found_source = None
    if key_from_env:
        key_found_source = f"Environment Variable ({env_var_name})"
    elif current_key:
        key_found_source = "Current Configuration"

    prompt_message = f"Enter your {provider_display_name} API key"
    if key_found_source:
        prompt_message += f" (found in {key_found_source}, press Enter to keep)"

    # Prompt for the key, hiding input and not showing the default value itself
    new_key = typer.prompt(
        prompt_message, default=default_key_value, hide_input=True, show_default=False
    )

    if not new_key:
        rich_print(
            f"[bold red]❌ {provider_display_name} API key cannot be empty.[/bold red]"
        )
        raise typer.Exit(code=1)

    # Return the key entered by the user, or the default if they just hit Enter
    return new_key


@app.command("configure")
def configure_settings():
    """
    Interactively configure API keys and default models for supported AI providers.

    Guides the user through selecting providers, entering keys, and choosing models.
    Updates the configuration file.
    """
    try:
        # Load the complete current configuration structure
        current_full_config = config_manager.load()
        current_providers_config = current_full_config.get("providers", {})
        current_default_provider = current_full_config.get("default_provider")

        # --- Provider Selection ---
        rich_print("\nSelect the AI providers you want to configure:")
        available_providers = list(PROVIDER_CONFIG.keys())

        # Pre-select providers that seem fully configured already
        pre_selected_providers = [
            p
            for p in available_providers
            if p in current_providers_config
            and current_providers_config[p].get("api_key")
            and current_providers_config[p].get("model")
        ]

        # Use questionary checkbox for multi-select
        providers_to_configure = questionary.checkbox(
            "Choose providers (Space to toggle, Enter to confirm):",
            choices=[
                # Use provider details from constants for display name
                questionary.Choice(
                    title=PROVIDER_CONFIG[p]["name"],
                    value=p,
                    checked=(p in pre_selected_providers),
                )
                for p in available_providers
            ],
        ).ask()

        # Handle cancellation or no selection
        if providers_to_configure is None:
            rich_print("Configuration cancelled.")
            raise typer.Exit()
        if not providers_to_configure:
            rich_print("[yellow]No providers selected for configuration.[/yellow]")
            # Check if *any* providers are configured at all
            if not config_manager.get_available_providers():
                rich_print("[yellow]No providers are configured yet.[/yellow]")
            raise typer.Exit()  # Exit if nothing selected

        # --- Configure Each Selected Provider ---
        new_providers_config = {}  # Store newly entered/confirmed settings
        configured_provider_names = (
            set()
        )  # Track which providers were successfully configured in this run

        for provider_key in providers_to_configure:
            provider_details = PROVIDER_CONFIG[provider_key]
            provider_display_name = provider_details["name"]
            rich_print(f"\n--- Configuring {provider_display_name} ---")

            # Get existing settings for this provider, if any
            current_provider_settings = current_providers_config.get(provider_key, {})

            # 1. API Key
            api_key = _prompt_for_api_key(
                provider_display_name=provider_display_name,
                env_var_name=provider_details.get("env_var"),
                current_key=current_provider_settings.get("api_key"),
            )

            # 2. Model Selection (using models from constants)
            model_choices = provider_details.get("models", [])
            selected_model = None

            if not model_choices:
                rich_print(
                    f"[yellow]Warning: No predefined models found for {provider_key}.[/yellow]"
                )
                # If no predefined models, perhaps allow manual input or skip?
                # For now, let's try to keep the existing model if possible.
                selected_model = current_provider_settings.get("model")
                if selected_model:
                    rich_print(f"[dim]Keeping existing model: {selected_model}[/dim]")
                else:
                    # If no existing and no choices, we can't proceed for this provider
                    rich_print(
                        f"[red]Cannot configure model for {provider_key}. Skipping.[/red]"
                    )
                    continue  # Skip to next provider
            else:
                # Ask user to select from the list
                selected_model = questionary.select(
                    f"Choose default {provider_display_name} model:",
                    choices=model_choices,
                    default=current_provider_settings.get(
                        "model"
                    ),  # Pre-select current default
                    instruction="(Use arrows, Enter to select)",
                ).ask()
                if selected_model is None:  # User cancelled model selection
                    rich_print(
                        f"Model selection for {provider_display_name} cancelled."
                    )
                    continue  # Skip saving this provider

            # Store new settings if both key and model are present
            if api_key and selected_model:
                new_providers_config[provider_key] = {
                    "api_key": api_key,
                    "model": selected_model,
                }
                configured_provider_names.add(provider_key)
            else:
                rich_print(
                    f"[yellow]Skipping save for {provider_display_name} due to missing info.[/yellow]"
                )

        # --- Merge and Finalize Configuration ---
        final_providers_config = current_providers_config.copy()
        final_providers_config.update(
            new_providers_config
        )  # Overwrite with new/confirmed settings

        # Determine providers that are valid *after* the merge
        all_valid_provider_keys = [
            p_key
            for p_key, p_conf in final_providers_config.items()
            if p_conf.get("api_key") and p_conf.get("model")
        ]

        # --- Select Default Provider ---
        selected_default_provider = current_default_provider
        if not all_valid_provider_keys:
            rich_print(
                "\n[bold yellow]⚠️ No providers are fully configured.[/bold yellow]"
            )
            selected_default_provider = None
        elif len(all_valid_provider_keys) == 1:
            # If only one valid provider, make it the default automatically
            selected_default_provider = all_valid_provider_keys[0]
            provider_name = PROVIDER_CONFIG[selected_default_provider]["name"]
            rich_print(
                f"\n[dim]Setting '{provider_name}' as the default provider.[/dim]"
            )
        else:
            # If multiple valid providers, ask the user to choose a default
            rich_print("\nSelect the default AI provider to use:")
            default_choices = [
                questionary.Choice(title=PROVIDER_CONFIG[p_key]["name"], value=p_key)
                for p_key in all_valid_provider_keys
            ]
            # Pre-select the current default if it's still valid
            prompt_default_value = (
                current_default_provider
                if current_default_provider in all_valid_provider_keys
                else None
            )
            # Ask user to select
            selected_default_provider = questionary.select(
                "Choose default provider:",
                choices=default_choices,
                default=prompt_default_value,
            ).ask()
            if selected_default_provider is None:  # User cancelled default selection
                rich_print(
                    "Default provider selection cancelled. Keeping previous default (if any)."
                )
                selected_default_provider = current_default_provider  # Keep old value

        # --- Save Final Configuration Structure ---
        final_config_data = {
            "default_provider": selected_default_provider,
            "providers": final_providers_config,
        }
        config_manager.save(final_config_data)

        # Confirm the default provider set
        if selected_default_provider and selected_default_provider in PROVIDER_CONFIG:
            provider_name = PROVIDER_CONFIG[selected_default_provider]["name"]
            rich_print(
                f"\n[bold]Default provider set to:[/bold] [cyan]{provider_name}[/cyan]"
            )
        elif not all_valid_provider_keys:
            rich_print(
                "[bold yellow]Configuration saved, but no default provider could be set (no providers fully configured).[/bold yellow]"
            )
        else:
            rich_print(
                "[yellow]Configuration saved, but no default provider selected.[/yellow]"
            )

    except ConfigError as e:
        rich_print(f"[bold red]❌ Configuration Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        rich_print("\nConfiguration cancelled by user.")
        raise typer.Exit()
    except Exception as e:
        # Catch unexpected errors during configuration
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e  # Re-raise Typer/Click exits
        rich_print(
            f"[bold red]❌ An unexpected error occurred during configuration: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()  # Print traceback for debugging
        raise typer.Exit(code=1)


@app.command("view")
def view_config():
    """View the current configuration for all providers."""
    try:
        if not config_manager.check_config_exists():
            rich_print("[yellow]⚠️ Configuration file not found or is empty.[/yellow]")
            rich_print(f"[dim]Expected location: {config_manager.config_path}[/dim]")
            rich_print("[yellow]💡 Run 'setup configure' to create it.[/yellow]")
            raise typer.Exit()

        config = config_manager.load()
        default_provider_key = config.get("default_provider")
        providers = config.get("providers", {})

        rich_print(f"[bold blue]Config File:[/bold blue] {config_manager.config_path}")

        # Display Default Provider
        if default_provider_key and default_provider_key in PROVIDER_CONFIG:
            provider_display_name = PROVIDER_CONFIG[default_provider_key]["name"]
            rich_print(
                f"[bold blue]Default Provider:[/bold blue] {provider_display_name} ({default_provider_key})"
            )
        elif default_provider_key:  # Default set but unknown?
            rich_print(
                f"[bold blue]Default Provider:[/bold blue] [yellow]'{default_provider_key}' (Unknown)[/yellow]"
            )
        else:
            rich_print(
                "[bold blue]Default Provider:[/bold blue] [yellow]Not Set[/yellow]"
            )

        # Display Configured Providers
        rich_print("\n[bold blue]Configured Providers:[/bold blue]")
        if not providers:
            rich_print("  [dim]None configured.[/dim]")
        else:
            for provider_key, settings in providers.items():
                # Get display name, fallback to key if unknown
                provider_display_name = PROVIDER_CONFIG.get(provider_key, {}).get(
                    "name", provider_key
                )
                status = "[red](Incomplete)"  # Assume incomplete initially
                if settings.get("api_key") and settings.get("model"):
                    status = "[green](OK)"

                rich_print(
                    f"\n  [bold {status.split('(')[1].split(')')[0]}]-> {provider_display_name} ({provider_key}) {status}[/]"
                )

                api_key = settings.get("api_key")
                model = settings.get("model", "[Not Set]")

                # Mask API key for display
                masked_key = "[Not Set]"
                if api_key and len(api_key) > 8:
                    masked_key = f"{api_key[:4]}...{api_key[-4:]}"
                elif api_key:  # Short key? Still hide it.
                    masked_key = "<hidden>"

                rich_print(f"    API Key: [sensitive]{masked_key}[/sensitive]")
                rich_print(f"    Model:   {model}")

    except ConfigError as e:
        rich_print(f"[bold red]❌ Error loading config: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        rich_print(
            f"[bold red]❌ Unexpected error viewing config: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)


@app.command("set-default")
def set_default_provider():
    """Select the default AI provider from currently configured ones."""
    try:
        current_full_config = config_manager.load()
        current_providers_config = current_full_config.get("providers", {})
        current_default = current_full_config.get("default_provider")

        # Find providers that are fully configured (have key and model)
        valid_provider_keys = [
            p_key
            for p_key, p_conf in current_providers_config.items()
            if p_conf.get("api_key")
            and p_conf.get("model")
            and p_key in PROVIDER_CONFIG
        ]

        if not valid_provider_keys:
            rich_print("[bold red]❌ No providers are fully configured yet.[/bold red]")
            rich_print(
                "[yellow]💡 Run 'setup configure' to add API keys and default models.[/yellow]"
            )
            raise typer.Exit(code=1)

        if len(valid_provider_keys) == 1:
            provider_name = PROVIDER_CONFIG[valid_provider_keys[0]]["name"]
            rich_print(
                f"[dim]Only one provider ('{provider_name}') is fully configured. It will be used as the default.[/dim]"
            )
            # Ensure it's actually set as default and save
            if current_full_config.get("default_provider") != valid_provider_keys[0]:
                current_full_config["default_provider"] = valid_provider_keys[0]
                config_manager.save(current_full_config)
                rich_print(f"[green]Set '{provider_name}' as default.[/green]")
            raise typer.Exit()  # Nothing more to do

        # Prompt user to select default from the valid ones
        rich_print("\nSelect the default AI provider to use:")
        default_choices = [
            questionary.Choice(title=PROVIDER_CONFIG[p_key]["name"], value=p_key)
            for p_key in valid_provider_keys
        ]
        # Pre-select current default if it's valid
        prompt_default_value = (
            current_default if current_default in valid_provider_keys else None
        )

        selected_default_provider = questionary.select(
            "Choose default provider:",
            choices=default_choices,
            default=prompt_default_value,
        ).ask()

        if selected_default_provider is None:
            rich_print("Default provider selection cancelled. No changes made.")
            raise typer.Exit()

        # Save the updated default provider
        current_full_config["default_provider"] = selected_default_provider
        config_manager.save(current_full_config)  # Save the whole structure back

        provider_name = PROVIDER_CONFIG[selected_default_provider]["name"]
        rich_print(
            f"\n[bold green]✅ Default provider successfully set to:[/bold green] [cyan]{provider_name}[/cyan]"
        )

    except ConfigError as e:
        rich_print(f"[bold red]❌ Configuration Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        rich_print("\nOperation cancelled.")
        raise typer.Exit()
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        rich_print(
            f"[bold red]❌ Unexpected error setting default provider: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)
