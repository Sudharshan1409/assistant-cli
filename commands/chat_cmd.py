# commands/chat_cmd.py
import traceback
from typing import Optional

import click  # Import click to check for click.exceptions.Exit
import questionary
import typer
from rich import print
from rich.markup import escape

from core.chat_session import ChatSession
from utils.ai_client import AIClient, AIClientError

# Import classes
from utils.config_manager import ConfigError, ConfigManager
from utils.session_manager import SessionError, SessionManager

app = typer.Typer(help="Create, resume (interactively), list, or delete chat sessions.")

# Instantiate managers
config_manager = ConfigManager()
session_manager = SessionManager()


# Helper function to initialize dependencies
def _initialize_dependencies():
    try:
        config = config_manager.get_required_config()
        ai_client = AIClient(api_key=config["openai_api_key"], model=config["model"])
        return ai_client
    except (
        ConfigError,
        ValueError,
        AIClientError,
        typer.Exit,
        click.exceptions.Exit,
    ) as e:  # Added click.exceptions.Exit
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):  # Check specifically
            raise  # Re-raise clean exits
        print(f"[bold red]❌ Initialization failed: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # --- MODIFIED --- Check if it's a clean Exit before treating as unexpected
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        # --- END MODIFIED ---
        print(
            f"[bold red]❌ Unexpected initialization error: {escape(str(e))}[/bold red]"
        )
        print("\n[yellow]--- Original Traceback ---[/yellow]")
        traceback.print_exc()
        print("[yellow]------------------------[/yellow]\n")
        raise typer.Exit(code=1)


# Helper function to start/resume chat session
def _start_chat_session(full_session_id: str):
    ai_client = _initialize_dependencies()
    try:
        chat_session = ChatSession(
            session_manager=session_manager,
            ai_client=ai_client,
            session_id=full_session_id,
        )
        chat_session.load_or_create()
        chat_session.run_interaction_loop()
    except FileNotFoundError:
        print(f"[bold red]❌ Session ID '{full_session_id}' not found.[/bold red]")
        raise typer.Exit(code=1)
    except (SessionError, AIClientError) as e:
        print(f"[bold red]❌ Chat Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # --- MODIFIED --- Check if it's a clean Exit before treating as unexpected
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        # --- END MODIFIED ---
        print(
            f"[bold red]❌ An unexpected error occurred during session: {escape(str(e))}[/bold red]"
        )
        print("\n[yellow]--- Original Traceback ---[/yellow]")
        traceback.print_exc()
        print("[yellow]------------------------[/yellow]\n")
        raise typer.Exit(code=1)


@app.command("new")
def new_chat(
    session_name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Optional name for the new chat session (generates if omitted)",
    )
):
    """Start a new chat session (optionally named, or named by AI)."""
    ai_client = _initialize_dependencies()
    try:
        chat_session = ChatSession(
            session_manager=session_manager,
            ai_client=ai_client,
            session_name=session_name,
        )
        chat_session.load_or_create()
        chat_session.run_interaction_loop()
    except (SessionError, AIClientError) as e:
        print(f"[bold red]❌ Chat Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # --- MODIFIED --- Check if it's a clean Exit before treating as unexpected
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        # --- END MODIFIED ---
        print(f"[bold red]❌ An unexpected error occurred: {escape(str(e))}[/bold red]")
        print("\n[yellow]--- Original Traceback ---[/yellow]")
        traceback.print_exc()
        print("[yellow]------------------------[/yellow]\n")
        raise typer.Exit(code=1)


@app.command("resume")
def resume_interactive_session():
    """Resume a previous chat session by selecting from a list."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            print("[yellow]No saved sessions found to resume.[/yellow]")
            raise typer.Exit()

        display_choices = [name for name, full_id in sessions_list] + ["[ Cancel ]"]

        selected_display_name = questionary.select(
            "Select a session to resume:", choices=display_choices, use_shortcuts=True
        ).ask()

        if selected_display_name is None or selected_display_name == "[ Cancel ]":
            print("Operation cancelled.")
            raise typer.Exit()  # This exit should not be caught as unexpected below

        selected_full_id = None
        for name, full_id in sessions_list:
            if name == selected_display_name:
                selected_full_id = full_id
                break

        if selected_full_id:
            print(f"Resuming session: {selected_display_name}")
            _start_chat_session(selected_full_id)
        else:
            print(
                f"[bold red]❌ Error finding full ID for selected session '{selected_display_name}'.[/bold red]"
            )
            raise typer.Exit(code=1)

    except SessionError as e:
        print(f"[bold red]❌ Error listing sessions: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        raise typer.Exit()  # This exit should not be caught as unexpected below
    except Exception as e:
        # --- MODIFIED --- Check if it's a clean Exit before treating as unexpected
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        # --- END MODIFIED ---
        print(
            f"[bold red]❌ An unexpected error occurred during resume: {escape(str(e))}[/bold red]"
        )
        print("\n[yellow]--- Original Traceback ---[/yellow]")
        traceback.print_exc()
        print("[yellow]------------------------[/yellow]\n")
        raise typer.Exit(code=1)


@app.command("list")
def list_all_sessions():
    """List all saved chat sessions (non-interactive)."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            print("[yellow]No saved sessions found.[/yellow]")
        else:
            print("[bold green]Saved sessions:[/bold green]")
            for display_name, full_id in sessions_list:
                print(f" - {display_name}")
    except SessionError as e:
        print(f"[bold red]❌ Error listing sessions: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # --- MODIFIED --- Check if it's a clean Exit before treating as unexpected
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        # --- END MODIFIED ---
        print(
            f"[bold red]❌ An unexpected error occurred during list: {escape(str(e))}[/bold red]"
        )
        print("\n[yellow]--- Original Traceback ---[/yellow]")
        traceback.print_exc()
        print("[yellow]------------------------[/yellow]\n")
        raise typer.Exit(code=1)


@app.command("delete")
def delete_session_interactive():
    """Delete a specific chat session by selecting from a list."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            print("[yellow]No saved sessions found to delete.[/yellow]")
            raise typer.Exit()

        display_choices = [name for name, full_id in sessions_list] + ["[ Cancel ]"]

        selected_display_name = questionary.select(
            "Select a session to delete:", choices=display_choices, use_shortcuts=True
        ).ask()

        if selected_display_name is None or selected_display_name == "[ Cancel ]":
            print("Operation cancelled.")
            raise typer.Exit()  # This exit should not be caught as unexpected below

        selected_full_id = None
        for name, full_id in sessions_list:
            if name == selected_display_name:
                selected_full_id = full_id
                break

        if not selected_full_id:
            print(
                f"[bold red]❌ Error finding full ID for selected session '{selected_display_name}'.[/bold red]"
            )
            raise typer.Exit(code=1)

        confirm = questionary.confirm(
            f"Are you sure you want to delete session '{selected_display_name}' (ID: {selected_full_id})?",
            default=False,
        ).ask()

        if not confirm:
            print("Deletion cancelled.")
            raise typer.Exit()  # This exit should not be caught as unexpected below

        session_manager.delete_session(selected_full_id)
        print(
            f"[bold green]✅ Session '{selected_display_name}' deleted successfully.[/bold green]"
        )

    except SessionError as e:
        print(
            f"[bold red]❌ Error during deletion process: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except FileNotFoundError as e:
        print(
            f"[bold red]❌ Error during deletion: Session file may have been removed externally. {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        raise typer.Exit()  # This exit should not be caught as unexpected below
    except Exception as e:
        # --- MODIFIED --- Check if it's a clean Exit before treating as unexpected
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        # --- END MODIFIED ---
        print(
            f"[bold red]❌ An unexpected error occurred during delete: {escape(str(e))}[/bold red]"
        )
        print("\n[yellow]--- Original Traceback ---[/yellow]")
        traceback.print_exc()
        print("[yellow]------------------------[/yellow]\n")
        raise typer.Exit(code=1)
