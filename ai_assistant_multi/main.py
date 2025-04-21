# main.py
"""
Main entry point for the AI CLI application.

Defines the Typer application and registers top-level commands
like 'prompt', 'setup', 'session', and 'version'.
"""

from pathlib import Path
from typing import Optional

import typer
from rich import print as rich_print

# Import command modules/apps/functions
from .commands import session_cmd, setup_cmd

# Import the implementation logic for direct prompt command
# This is needed because the 'prompt' command is defined at the top level here
from .commands.session_cmd import direct_prompt_logic

# Import constants used directly in this file
from .constants import APP_NAME, APP_VERSION, OUTPUT_FORMAT_CHOICES

# Create the main Typer application instance
app = typer.Typer(
    name=APP_NAME,
    help="A command-line interface for interacting with AI models.",
    add_completion=True,
)

# Add subcommands defined in other modules
app.add_typer(
    setup_cmd.app,
    name="setup",
    help="Configure application settings (API keys, models, defaults).",
)
app.add_typer(
    session_cmd.app,
    name="session",
    help="Manage interactive chat sessions (new, list, delete, resume).",
)


# Define the top-level 'prompt' command
@app.command("prompt")
def prompt_command_wrapper(
    prompt_text: str = typer.Argument(..., help="The prompt/instruction for the AI."),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to a file to include as context (ignored if piping data via stdin).",
        exists=True,  # Ensure the file exists
        file_okay=True,  # Allow files
        dir_okay=False,  # Disallow directories
        readable=True,  # Ensure the file is readable
        resolve_path=True,  # Resolve to an absolute path
    ),
    output_format: str = typer.Option(
        "markdown",  # Default format
        "--output-format",
        "-of",
        # Dynamically create help text listing choices from constants
        help=f"Output format ({', '.join(OUTPUT_FORMAT_CHOICES)}).",
        case_sensitive=False,  # Allow case-insensitive matching (e.g., JSON, json)
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file",
        "-o",
        help="Path to save the output instead of printing to console.",
        dir_okay=False,  # Disallow directories
        writable=True,  # Ensure the location is writable
        resolve_path=True,  # Resolve to an absolute path
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="AI provider to use (e.g., openai, google). Overrides default.",
        case_sensitive=False,
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Specific AI model to use. Overrides default for the chosen provider.",
    ),
):
    """
    Sends a single prompt (optionally with context/overrides) to the AI.

    Prints the response (default: stdout) or saves it to a file.
    Status messages and token usage are printed to stderr.
    Piped data (stdin) takes precedence over the --file option.
    """
    # Delegate the core logic to the function imported from session_cmd
    direct_prompt_logic(
        prompt_text=prompt_text,
        file=file,
        output_format=output_format,
        output_file=output_file,
        provider_override=provider,
        model_override=model,
    )


# Define the top-level 'version' command
@app.command("version")
def show_version():
    """Displays the application's version."""
    rich_print(f"name: {APP_NAME} version: {APP_VERSION}")


# Entry point for running the script directly
if __name__ == "__main__":
    app()
