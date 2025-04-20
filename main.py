# main.py
import typer

# Import the command apps (Typer instances)
from commands import chat_cmd, setup_cmd  # Use new filenames if changed

# Optional: Create a main app instance
app = typer.Typer(
    name="ai-cli",
    help="A command-line interface for interacting with AI models.",
    add_completion=False,  # Optional: disable shell completion if not needed
)

# Add the command groups (Typer apps) as subcommands
app.add_typer(setup_cmd.app, name="setup", help="Configure application settings")
app.add_typer(chat_cmd.app, name="chat", help="Manage and interact with chat sessions")


# Optional: Add a top-level command if needed
@app.command("version")
def show_version():
    """Show application version."""
    # In a real app, you'd import this from __version__ or setup.py
    print("AI-CLI v1.0.0 (Refactored)")


if __name__ == "__main__":
    app()
