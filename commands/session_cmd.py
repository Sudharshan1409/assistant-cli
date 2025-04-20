# commands/session_cmd.py
import json
import re  # Import re for regex post-processing
import sys
import traceback
from pathlib import Path
from typing import Optional

import click
import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape

# Import ChatSession to access constants like CODE_THEME, MAX_UPLOAD_SIZE_KB etc.
from core.chat_session import ChatSession
from utils.ai_client import AIClient, AIClientError

# Import classes
from utils.config_manager import ConfigError, ConfigManager
from utils.session_manager import SessionError, SessionManager

# Create a console instance
console = Console()

# Define allowed output formats (used by direct_prompt)
OUTPUT_FORMAT_CHOICES = ["markdown", "raw", "json"]

# --- MODIFIED Typer App definition ---
# Changed help text
app = typer.Typer(help="Manage AI chat sessions (new, resume, list, delete).")
# --- END MODIFICATION ---

# Instantiate managers
config_manager = ConfigManager()
session_manager = SessionManager()


# Helper function to initialize dependencies (remains the same)
def _initialize_dependencies():
    """Initializes AIClient based on configuration."""
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
    ) as e:
        # Check if it's a clean Exit exception first
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e  # Re-raise clean exits
        # Otherwise, print specific initialization failure message
        console.print(
            f"[bold red]❌ Initialization failed: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)  # Exit with error code
    except Exception as e:
        # Catch any other unexpected exceptions during initialization
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e  # Re-raise clean exits
        console.print(
            f"[bold red]❌ Unexpected initialization error: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()  # Print full traceback for unexpected errors
        raise typer.Exit(code=1)  # Exit with error code


# Helper function to start/resume chat session (remains the same)
def _start_chat_session(full_session_id: str):
    """Initializes and starts/resumes an interactive chat session."""
    ai_client = _initialize_dependencies()
    try:
        # Create and run the chat session using the ChatSession class
        chat_session = ChatSession(
            session_manager=session_manager,
            ai_client=ai_client,
            session_id=full_session_id,
        )
        chat_session.load_or_create()
        chat_session.run_interaction_loop()
    except FileNotFoundError:
        # Handle case where the specified session file isn't found
        console.print(
            f"[bold red]❌ Session ID '{full_session_id}' not found.[/bold red]"
        )
        raise typer.Exit(code=1)
    except (SessionError, AIClientError) as e:
        # Handle specific errors related to session management or AI calls
        console.print(f"[bold red]❌ Chat Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        # Catch any other unexpected error during the session
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e  # Re-raise clean exits
        console.print(
            f"[bold red]❌ An unexpected error occurred during session: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()  # Print traceback for debugging
        raise typer.Exit(code=1)


# --- Session Management Commands ---
# These commands are defined under this Typer app ('app')


@app.command("new")
def new_chat(
    session_name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Optional name for the new chat session (generates if omitted)",
    )
):
    """Start a new chat session."""
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
        console.print(f"[bold red]❌ Chat Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        console.print(
            f"[bold red]❌ An unexpected error occurred creating new session: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)


@app.command("resume")
def resume_interactive_session():
    """Resume a previous chat session by selecting from a list."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            console.print("[yellow]No saved sessions found to resume.[/yellow]")
            raise typer.Exit()

        choices = [Choice(title=name, value=full_id) for name, full_id in sessions_list]
        selected_full_id = questionary.select(
            "Select a session to resume (Ctrl+C to cancel):",
            choices=choices,
            use_shortcuts=True,
        ).ask()

        if selected_full_id is None:
            console.print("Operation cancelled.")
            raise typer.Exit()

        selected_display_name = "[Unknown]"
        for name, f_id in sessions_list:
            if f_id == selected_full_id:
                selected_display_name = name
                break

        console.print(f"Resuming session: {selected_display_name}")
        _start_chat_session(selected_full_id)

    except SessionError as e:
        console.print(
            f"[bold red]❌ Error listing sessions: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\nOperation cancelled by user.")
        raise typer.Exit()
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        console.print(
            f"[bold red]❌ An unexpected error occurred during resume: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)


@app.command("list")
def list_all_sessions():
    """List all saved chat sessions."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            console.print("[yellow]No saved sessions found.[/yellow]")
        else:
            console.print("[bold green]Saved sessions:[/bold green]")
            for display_name, full_id in sessions_list:
                console.print(f" - {display_name}")
    except SessionError as e:
        console.print(
            f"[bold red]❌ Error listing sessions: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        console.print(
            f"[bold red]❌ An unexpected error occurred during list: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)


@app.command("delete")
def delete_sessions_interactive():
    """Delete one or more chat sessions by selecting from a list."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            console.print("[yellow]No saved sessions found to delete.[/yellow]")
            raise typer.Exit()

        choices = [Choice(title=name, value=full_id) for name, full_id in sessions_list]
        console.print("\n[dim]Use arrow keys to navigate.")
        console.print("[dim]<Space> to toggle selection.")
        console.print("[dim]<a> to toggle all selections.")
        console.print("[dim]<Enter> to confirm selections.")
        console.print("[dim]Ctrl+C to cancel.[/dim]")

        selected_full_ids = questionary.checkbox(
            "Select sessions to delete:", choices=choices
        ).ask()

        if selected_full_ids is None:
            console.print("Operation cancelled by user.")
            raise typer.Exit()
        if not selected_full_ids:
            console.print("[yellow]No sessions selected.[/yellow]")
            raise typer.Exit()

        id_to_name_map = {full_id: name for name, full_id in sessions_list}
        names_to_delete = [id_to_name_map.get(fid, fid) for fid in selected_full_ids]
        confirm_message = f"Are you sure you want to delete the following {len(selected_full_ids)} session(s)?\n"
        for name in sorted(names_to_delete):
            confirm_message += f"  - {name}\n"
        confirm = questionary.confirm(confirm_message, default=False).ask()

        if not confirm:
            console.print("Deletion cancelled.")
            raise typer.Exit()

        success_count = 0
        fail_count = 0
        failed_sessions_info = []
        console.print("\n[cyan]Deleting selected sessions...[/cyan]")
        for full_id in selected_full_ids:
            display_name = id_to_name_map.get(full_id, full_id)
            try:
                session_manager.delete_session(full_id)
                success_count += 1
            except (SessionError, FileNotFoundError) as e:
                fail_count += 1
                failed_sessions_info.append((display_name, str(e)))
            except Exception as e:
                fail_count += 1
                failed_sessions_info.append(
                    (display_name, f"Unexpected error: {str(e)}")
                )
                console.print(f"[red]! Unexpected error deleting {display_name}:[/red]")
                traceback.print_exc()

        console.print("-" * 20)
        if success_count > 0:
            console.print(
                f"[bold green]✅ Successfully deleted {success_count} session(s).[/bold green]"
            )
        if fail_count > 0:
            console.print(
                f"[bold yellow]⚠️ Failed to delete {fail_count} session(s):[/bold yellow]"
            )
            for name, error in failed_sessions_info:
                console.print(f"  - {name}: {escape(error)}")
        console.print("-" * 20)

    except SessionError as e:
        console.print(
            f"[bold red]❌ Error listing sessions for deletion: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console.print("\nOperation cancelled by user.")
        raise typer.Exit()
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        console.print(
            f"[bold red]❌ An unexpected error occurred during delete: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc()
        raise typer.Exit(code=1)


# --- Direct Prompt Command Implementation (Remains Here) ---
# Note: This function is decorated with @typer.command later in main.py
# We define the implementation logic here.


def direct_prompt_logic(  # Renamed implementation function slightly
    prompt_text: str,
    file: Optional[Path],
    output_format: str,
    output_file: Optional[Path],
):
    """Core logic for handling direct prompts."""
    # Validate Output Format
    if output_format.lower() not in OUTPUT_FORMAT_CHOICES:
        console.print(
            f"[bold red]❌ Invalid output format '{output_format}'. Choose from: {', '.join(OUTPUT_FORMAT_CHOICES)}[/bold red]"
        )
        raise typer.Exit(code=1)
    output_format = output_format.lower()

    ai_client = _initialize_dependencies()

    stdin_content = None
    file_content = None
    file_name = None
    final_user_prompt_instruction = prompt_text

    # Check Stdin
    if not sys.stdin.isatty():
        console.print("[dim]Reading data from stdin...[/dim]")
        stdin_content = sys.stdin.read()
        if not stdin_content:
            console.print("[bold yellow]⚠️ Empty stdin data.[/bold yellow]")
        else:
            try:  # Size check
                stdin_size_bytes = len(stdin_content.encode("utf-8"))
                max_size_bytes = ChatSession.MAX_UPLOAD_SIZE_KB * 1024
                if stdin_size_bytes > max_size_bytes:
                    console.print("[bold red]❌ Stdin data too large...[/bold red]")
                    raise typer.Exit(code=1)
                console.print(
                    f"[dim]Read {stdin_size_bytes / 1024:.1f} KB from stdin.[/dim]"
                )
                if file:
                    console.print(
                        f"[yellow]⚠️ Ignoring --file ('{file.name}') due to stdin data.[/yellow]"
                    )
                    file = None
            except Exception as e:
                console.print(
                    f"[bold red]❌ Error processing stdin data: {escape(str(e))}[/bold red]"
                )
                traceback.print_exc()
                raise typer.Exit(code=1)

    # Read File (if applicable)
    if file:
        file_name = file.name
        try:  # Size/Ext checks
            file_size = file.stat().st_size
            max_size_bytes = ChatSession.MAX_UPLOAD_SIZE_KB * 1024
            if file_size > max_size_bytes:
                console.print(
                    f"[bold red]❌ File '{file_name}' too large...[/bold red]"
                )
                raise typer.Exit(code=1)
            if file_size == 0:
                console.print(
                    f"[bold yellow]⚠️ File '{file_name}' is empty.[/bold yellow]"
                )
            if ChatSession.ALLOWED_EXTENSIONS:
                file_ext = file.suffix.lower()
                if file_ext not in ChatSession.ALLOWED_EXTENSIONS:
                    allowed_str = ", ".join(ChatSession.ALLOWED_EXTENSIONS)
                    console.print(
                        f"[bold red]❌ Invalid file type '{file_ext}'...[/bold red]"
                    )
                    raise typer.Exit(code=1)

            file_content = file.read_text(encoding="utf-8")
            console.print(
                f"[dim]Including file: {file_name} ({file_size / 1024:.1f} KB)[/dim]"
            )
        except Exception as e:  # Catch all file errors
            if isinstance(e, (typer.Exit, click.exceptions.Exit)):
                raise e
            console.print(
                f"[bold red]❌ Unexpected error processing file '{file_name}': {escape(str(e))}[/bold red]"
            )
            traceback.print_exc()
            raise typer.Exit(code=1)

    # Construct context prefix
    context_prefix = ""
    if stdin_content:
        context_prefix = f"[Data from standard input]\n\n--- Input Data Start ---\n{stdin_content}\n--- Input Data End ---\n\n"
    elif file_content:
        escaped_fname = escape(file_name or "file")
        context_prefix = f"[User uploaded file: '{escaped_fname}']\n\n--- File Content Start ({escaped_fname}) ---\n{file_content}\n--- File Content End ({escaped_fname}) ---\n\n"

    # Construct final prompt with format instructions
    instruction_suffix = ""
    if output_format == "json":
        instruction_suffix = "\n\nRESPONSE FORMATTING INSTRUCTIONS: Your entire response MUST be ONLY a single, valid JSON object or array..."
        console.print("[dim]Requesting JSON output...")
    elif output_format == "raw":
        instruction_suffix = "\n\nRESPONSE FORMATTING INSTRUCTIONS: Your entire response MUST be ONLY the requested raw text..."
        console.print("[dim]Requesting raw output...")

    final_prompt_to_send = (
        context_prefix + final_user_prompt_instruction + instruction_suffix
    )
    messages = [{"role": "user", "content": final_prompt_to_send}]

    # Call AI and handle output
    try:
        with console.status("[yellow]🧠 Thinking...[/yellow]", spinner="dots"):
            ai_reply = ai_client.get_completion(messages)
        if not ai_reply:
            console.print("[italic yellow](Empty response received)[/italic]")
            raise typer.Exit()

        # Post-processing and Output/Save
        processed_reply = ai_reply.strip()
        output_content = ai_reply
        if output_format in ["raw", "json"]:
            match = re.match(
                r"^\s*```(?:\w*\s*)?\n?(.*?)\n?```\s*$",
                processed_reply,
                re.DOTALL | re.IGNORECASE,
            )
            if match:
                processed_reply = match.group(1).strip()
            output_content = processed_reply

        if output_file:
            try:  # Save to file
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(output_content, encoding="utf-8")
                console.print(
                    f"[bold green]✅ Output saved to:[/bold green] {output_file}"
                )
            except Exception as e:  # Catch save errors
                if isinstance(e, (typer.Exit, click.exceptions.Exit)):
                    raise e
                console.print(
                    f"[bold red]❌ Error saving output file: {escape(str(e))}[/bold red]"
                )
                traceback.print_exc()
                raise typer.Exit(code=1)
        else:  # Print to console
            if output_format == "markdown":
                console.print(Markdown(ai_reply, code_theme=ChatSession.CODE_THEME))
            elif output_format == "raw":
                print(processed_reply)  # Use standard print
            elif output_format == "json":
                try:
                    parsed_json = json.loads(processed_reply)
                    print(json.dumps(parsed_json, indent=2))  # Use standard print
                except json.JSONDecodeError:
                    console.print(
                        "[bold yellow]⚠️ Not valid JSON. Raw output:[/bold yellow]"
                    )
                    print(processed_reply)  # Use standard print

    except AIClientError as e:
        console.print(f"[bold red]\n❌ AI Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except Exception as e:
        if isinstance(e, (typer.Exit, click.exceptions.Exit)):
            raise e
        console.print(f"[bold red]\n❌ Unexpected Error: {escape(str(e))}[/bold red]")
        traceback.print_exc()
        raise typer.Exit(code=1)
