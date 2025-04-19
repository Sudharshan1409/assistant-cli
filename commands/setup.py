import click
import typer
from rich import print
from utils.config_handler import save_config

app = typer.Typer()

MODEL_CHOICES = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"]


@app.command("setup")
def setup(
    openai_api_key: str = typer.Option(
        None, "--openai-api-key", "-k", help="Your OpenAI API key"
    ),
    model: str = typer.Option(
        None,
        "--model",
        "-m",
        help="Model to use",
        show_choices=True,
        case_sensitive=False,
    ),
):
    """
    Configure your AI Assistant credentials and settings.
    """
    if not openai_api_key:
        openai_api_key = typer.prompt("Enter your OpenAI API key")

    if not model:
        model = typer.prompt(
            "Choose your model", type=click.Choice(MODEL_CHOICES, case_sensitive=False)
        )

    config_data = {"openai_api_key": openai_api_key, "model": model}

    save_config(config_data)
    print(
        f"[bold green]✅ Configuration saved successfully with model:[/bold green] {model}"
    )
