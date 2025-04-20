# commands/setup_cmd.py (or keep name setup.py)
import click  # Keep for click.Choice
import typer
from rich import print

from utils.config_manager import ConfigError, ConfigManager  # Import the class

# Maybe define choices globally or within the class/command context
MODEL_CHOICES = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"]

app = typer.Typer(help="Configure application settings.")

# Instantiate the manager (could be passed via context if needed)
config_manager = ConfigManager()


@app.command("configure")  # Changed command name slightly for clarity
def configure_settings(
    openai_api_key: str = typer.Option(
        None,
        "--openai-api-key",
        "-k",
        help="Your OpenAI API key (leave empty for prompt)",
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use (leave empty for prompt)",
        # click.Choice is better handled in the prompt logic now
    ),
):
    """
    Configure your AI Assistant credentials and settings interactively.
    """
    current_config = (
        config_manager.load()
    )  # Load existing to pre-fill prompts if needed

    if not openai_api_key:
        openai_api_key = typer.prompt(
            "Enter your OpenAI API key",
            default=current_config.get("openai_api_key", None),  # Suggest existing key
        )

    if not model:
        # Use rich/questionary later for better prompts, or stick to click.Choice
        model = typer.prompt(
            "Choose model",
            type=click.Choice(MODEL_CHOICES, case_sensitive=False),
            default=current_config.get("model", None),  # Suggest existing model
            show_choices=True,
        )
    elif model not in MODEL_CHOICES:
        print(
            f"[bold red]❌ Invalid model '{model}'. Choose from: {', '.join(MODEL_CHOICES)}[/bold red]"
        )
        raise typer.Exit(code=1)

    config_data = {"openai_api_key": openai_api_key, "model": model}

    try:
        config_manager.save(config_data)
        # Confirmation is now printed within config_manager.save()
        print(f"[bold cyan]Using model:[/bold cyan] {model}")
    except ConfigError as e:
        print(f"[bold red]❌ Error saving configuration: {e}[/bold red]")
        raise typer.Exit(code=1)


# You might add commands here to view current config, delete config etc.
@app.command("view")
def view_config():
    """View the current configuration."""
    if not config_manager.check_config_exists():
        print(
            "[yellow]⚠️ No configuration file found. Run 'setup configure' first.[/yellow]"
        )
        raise typer.Exit()

    try:
        config = config_manager.load()
        print("[bold blue]Current Configuration:[/bold blue]")
        # Mask API key partially for security
        api_key = config.get("openai_api_key", "Not Set")
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else api_key
        print(f"  API Key: {masked_key}")
        print(f"  Model: {config.get('model', 'Not Set')}")
        print(f"  Config File: {config_manager.config_path}")
    except ConfigError as e:
        print(f"[bold red]❌ Error loading configuration: {e}[/bold red]")
        raise typer.Exit(code=1)
