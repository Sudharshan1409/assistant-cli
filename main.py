# main.py
from pathlib import Path  # Import Path for type hint
from typing import Optional  # Ensure Optional is imported

import typer

# Import command modules/apps/functions
from commands import setup_cmd
from commands.session_cmd import OUTPUT_FORMAT_CHOICES  # Import choices for help text
from commands.session_cmd import direct_prompt_logic  # Import the implementation logic
from commands.session_cmd import app as session_app  # Import the session Typer app

# Create the main app instance
app = typer.Typer(
    name="ai-cli",
    help="A command-line interface for interacting with AI models.",
    add_completion=False,
)

# Add setup commands
app.add_typer(setup_cmd.app, name="setup", help="Configure application settings")

# Add session management commands under 'session'
app.add_typer(
    session_app, name="session", help="Manage chat sessions (new, list, delete, resume)"
)


# Add direct prompt command at the top level using a wrapper function
@app.command("prompt")
def prompt_command_wrapper(
    prompt_text: str = typer.Argument(..., help="The prompt/instruction for the AI."),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="Path to a file to include as context (ignored if piping data via stdin).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
    ),
    output_format: str = typer.Option(
        "markdown",
        "--output-format",
        "-of",
        help=f"Output format ({', '.join(OUTPUT_FORMAT_CHOICES)}).",
        case_sensitive=False,
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file",
        "-o",
        help="Path to save the output instead of printing to console.",
        dir_okay=False,
        writable=True,
        resolve_path=True,
    ),
):
    """
    Sends a single prompt (optionally with context) to the AI.
    Prints the response or saves it to a file.
    Piped data (stdin) takes precedence over the --file option.
    """
    # Call the actual implementation function from session_cmd
    direct_prompt_logic(
        prompt_text=prompt_text,
        file=file,
        output_format=output_format,
        output_file=output_file,
    )


# Optional: Add a top-level version command
@app.command("version")
def show_version():
    """Show application version."""
    # In a real app, you'd import this from __version__ or setup.py
    rich_print("AI-CLI v1.2.0 (Refactored + Features)")  # Use rich_print


if __name__ == "__main__":
    # Import rich print for potential use in __main__ block if needed
    from rich import print as rich_print

    app()
