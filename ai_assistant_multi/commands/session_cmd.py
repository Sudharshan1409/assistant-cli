# commands/session_cmd.py
"""
Handles the 'session' subcommands and the core logic for direct prompts.

Manages interactive chat sessions (new, resume, list, delete) and
processes single prompts with context (stdin, files) and output options.
"""

import json
import re
import sys
import traceback
from pathlib import Path
from typing import Optional

import questionary
import typer
from questionary import Choice
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape

# Import relevant constants
from ..constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    DEFAULT_CODE_THEME,
    MAX_UPLOAD_SIZE_KB,
    OUTPUT_FORMAT_CHOICES,
)

# Import core components and utilities
from ..core.chat_session import ChatSession
from ..utils.base_client import AIClientError, BaseAIClient
from ..utils.config_manager import PROVIDER_CONFIG, ConfigError, ConfigManager

# Import specific client implementations (needed for instantiation)
from ..utils.google_client import GoogleAIClient
from ..utils.openai_client import OpenAIClient
from ..utils.session_manager import SessionError, SessionManager

# Console instances for distinct output streams
console = Console()  # For standard output (e.g., Markdown responses, prompts)
console_stderr = Console(stderr=True, style="dim")  # For status, errors, metadata

# Typer app for 'session' subcommands
app = typer.Typer(help="Manage AI chat sessions (new, resume, list, delete).")

# Instantiate managers
config_manager = ConfigManager()
session_manager = SessionManager()


def _initialize_dependencies(
    provider_override: Optional[str] = None, model_override: Optional[str] = None
) -> BaseAIClient:
    """
    Loads configuration and initializes the appropriate AIClient.

    Determines the provider and model based on overrides or defaults from config.
    Validates configuration and instantiates the correct client class.

    Args:
        provider_override: Specific provider key (e.g., 'openai') to use.
        model_override: Specific model name to use.

    Returns:
        An instance of a BaseAIClient subclass (e.g., OpenAIClient).

    Raises:
        typer.Exit: If configuration is missing, invalid, or dependencies fail.
    """
    try:
        config = config_manager.load()

        # 1. Determine Provider Key
        provider_key = provider_override or config.get("default_provider")
        if not provider_key:
            console_stderr.print(
                "[bold red]❌ No AI provider specified and no default set.[/]"
            )
            console_stderr.print(
                "[yellow]💡 Use --provider <name> or run 'setup configure'[/]"
            )
            raise typer.Exit(code=1)

        provider_key = provider_key.lower()
        if provider_key not in PROVIDER_CONFIG:
            console_stderr.print(f"[bold red]❌ Unknown provider: '{provider_key}'[/]")
            console_stderr.print(f"Supported: {', '.join(PROVIDER_CONFIG.keys())}")
            raise typer.Exit(code=1)

        # 2. Get Provider Settings from Config
        provider_settings = config_manager.get_provider_config(provider_key)
        if not provider_settings:
            provider_name = PROVIDER_CONFIG[provider_key]["name"]
            console_stderr.print(
                f"[bold red]❌ Provider '{provider_name}' not configured.[/]"
            )
            console_stderr.print(
                f"[yellow]💡 Run 'setup configure' for {provider_name}.[/]"
            )
            raise typer.Exit(code=1)

        # 3. Determine Model Name
        model_name = model_override or provider_settings.get("model")
        if not model_name:
            provider_name = PROVIDER_CONFIG[provider_key]["name"]
            console_stderr.print(
                f"[bold red]❌ No model configured for {provider_name}.[/]"
            )
            console_stderr.print(
                "[yellow]💡 Use --model <name> or run 'setup configure'.[/]"
            )
            raise typer.Exit(code=1)

        # 4. Get API Key
        api_key = provider_settings.get("api_key")
        if not api_key:
            provider_name = PROVIDER_CONFIG[provider_key]["name"]
            console_stderr.print(
                f"[bold red]❌ API key not found for {provider_name}.[/]"
            )
            console_stderr.print("[yellow]💡 Run 'setup configure'.[/]")
            raise typer.Exit(code=1)

        # 5. Instantiate the Correct Client
        provider_name = PROVIDER_CONFIG[provider_key]["name"]
        console_stderr.print(
            f"Using Provider: [cyan]{provider_name}[/], Model: [cyan]{model_name}[/]"
        )

        if provider_key == "openai":
            return OpenAIClient(api_key=api_key, model=model_name)
        elif provider_key == "google":
            return GoogleAIClient(api_key=api_key, model=model_name)
        # Add elif for other providers here
        else:
            # Should be caught by the check against PROVIDER_CONFIG keys earlier
            console_stderr.print(
                f"[bold red]❌ Internal Error: Unsupported provider '{provider_key}'.[/]"
            )
            raise typer.Exit(code=1)

    except ConfigError as e:  # Catch config-specific errors
        console_stderr.print(
            f"[bold red]❌ Configuration Error: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except (ValueError, AIClientError) as e:  # Catch validation/client init errors
        console_stderr.print(
            f"[bold red]❌ Initialization failed: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except typer.Exit as e:  # Re-raise typer exits
        raise e
    except Exception as e:  # Catch unexpected errors
        console_stderr.print(
            f"[bold red]❌ Unexpected initialization error: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)


def _start_chat_session(
    full_session_id: str,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
):
    """
    Helper to initialize dependencies and run an interactive chat session.

    Args:
        full_session_id: The unique ID (name_uuid) of the session to start/resume.
        provider_override: Optional provider key to override the default.
        model_override: Optional model name to override the default.
    """
    try:
        # Initialize client (handles config loading/validation)
        ai_client = _initialize_dependencies(
            provider_override=provider_override, model_override=model_override
        )

        # Create and run the chat session
        chat_session = ChatSession(
            session_manager=session_manager,
            ai_client=ai_client,
            session_id=full_session_id,
        )
        chat_session.load_or_create()  # Loads or initializes session state
        chat_session.run_interaction_loop()  # Starts the user interaction

    except FileNotFoundError:  # Specific error for session not found
        console_stderr.print(
            f"[bold red]❌ Session ID '{full_session_id}' not found.[/bold red]"
        )
        raise typer.Exit(code=1)
    except (
        SessionError,
        AIClientError,
    ) as e:  # Catch session or AI errors during setup/run
        console_stderr.print(f"[bold red]❌ Chat Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except typer.Exit as e:  # Re-raise exits from initialization or chat loop
        raise e
    except Exception as e:  # Catch unexpected errors during session run
        console_stderr.print(
            f"[bold red]❌ An unexpected error occurred during session: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)


# --- Session Management Commands ---


@app.command("new")
def new_chat(
    session_name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Optional name for the new chat session."
    ),
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="AI provider (e.g., openai, google). Overrides default.",
        case_sensitive=False,
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Specific AI model to use for this session. Overrides default.",
    ),
):
    """Start a new interactive chat session."""
    try:
        ai_client = _initialize_dependencies(
            provider_override=provider, model_override=model
        )
        # ChatSession handles generating ID if name is None but session_name is passed
        chat_session = ChatSession(
            session_manager=session_manager,
            ai_client=ai_client,
            session_name=session_name,  # Pass name if provided
        )
        chat_session.load_or_create()  # Creates or loads based on generated/provided ID
        chat_session.run_interaction_loop()
    except (SessionError, AIClientError, typer.Exit) as e:
        # Errors during init or run are caught and printed by _initialize or ChatSession
        if not isinstance(e, typer.Exit):  # Avoid double printing if already handled
            console_stderr.print(
                f"[bold red]❌ Chat Error: {escape(str(e))}[/bold red]"
            )
        raise typer.Exit(code=1)  # Ensure exit code
    except Exception as e:
        console_stderr.print(
            f"[bold red]❌ Unexpected error creating new session: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)


@app.command("resume")
def resume_interactive_session(
    provider: Optional[str] = typer.Option(
        None,
        "--provider",
        "-p",
        help="Override AI provider for this session.",
        case_sensitive=False,
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Override specific AI model for this session.",
    ),
):
    """Resume a previous chat session by selecting from a list."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            console.print(
                "[yellow]No saved sessions found to resume.[/yellow]"
            )  # To stdout
            raise typer.Exit()

        # Prepare choices for questionary
        choices = [
            Choice(title=name, value=full_id)  # Display name, return full ID
            for name, full_id in sessions_list  # Assumes list_sessions returns (display_name, full_id)
        ]

        # Ask user to select a session
        selected_full_id = questionary.select(
            "Select a session to resume:",
            choices=choices,
            use_shortcuts=True,
        ).ask()

        if selected_full_id is None:  # User cancelled (Ctrl+C)
            console.print("Operation cancelled.")  # To stdout
            raise typer.Exit()

        # Find display name for confirmation message (optional)
        selected_display_name = next(
            (name for name, f_id in sessions_list if f_id == selected_full_id),
            "[Unknown]",
        )
        console.print(f"Resuming: {selected_display_name}")  # To stdout

        # Start the selected session using the helper
        _start_chat_session(
            selected_full_id, provider_override=provider, model_override=model
        )

    except SessionError as e:  # Error listing sessions
        console_stderr.print(
            f"[bold red]❌ Error listing sessions: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except KeyboardInterrupt:  # User cancelled selection
        console_stderr.print("\nOperation cancelled by user.")
        raise typer.Exit()
    except typer.Exit as e:  # Re-raise exits from _start_chat_session
        raise e
    except Exception as e:  # Catch unexpected errors during resume process
        console_stderr.print(
            f"[bold red]❌ An unexpected error occurred during resume: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)


@app.command("list")
def list_all_sessions():
    """List all saved chat sessions, sorted by modification time (latest first)."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            console.print("[yellow]No saved sessions found.[/yellow]")  # Stdout
        else:
            console.print("[bold green]Saved sessions:[/bold green]")  # Stdout
            for display_name, _ in sessions_list:  # Only show display name
                console.print(f" - {display_name}")  # Stdout
    except SessionError as e:
        console_stderr.print(
            f"[bold red]❌ Error listing sessions: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except Exception as e:
        console_stderr.print(
            f"[bold red]❌ An unexpected error occurred during list: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)


@app.command("delete")
def delete_sessions_interactive():
    """Delete one or more chat sessions by selecting from a list."""
    try:
        sessions_list = session_manager.list_sessions()
        if not sessions_list:
            console.print(
                "[yellow]No saved sessions found to delete.[/yellow]"
            )  # Stdout
            raise typer.Exit()

        # Prepare choices for checkbox
        choices = [Choice(title=name, value=full_id) for name, full_id in sessions_list]

        # Instructions for checkbox
        console.print(
            "\n[dim]Use arrow keys, <Space> to toggle, <a> to toggle all, <Enter> to confirm.[/dim]"
        )

        # Ask user to select sessions to delete
        selected_full_ids = questionary.checkbox(
            "Select sessions to delete (Ctrl+C to cancel):", choices=choices
        ).ask()

        # Handle cancellation or no selection
        if selected_full_ids is None:
            console.print("Operation cancelled.")  # Stdout
            raise typer.Exit()
        if not selected_full_ids:
            console.print("[yellow]No sessions selected.[/yellow]")  # Stdout
            raise typer.Exit()

        # Confirm deletion
        id_to_name_map = {full_id: name for name, full_id in sessions_list}
        names_to_delete = sorted(
            [id_to_name_map.get(fid, fid) for fid in selected_full_ids]
        )
        confirm_message = f"Are you sure you want to delete the following {len(selected_full_ids)} session(s)?\n"
        confirm_message += "\n".join([f"  - {name}" for name in names_to_delete])
        confirm = questionary.confirm(confirm_message, default=False).ask()

        if not confirm:
            console.print("Deletion cancelled.")  # Stdout
            raise typer.Exit()

        # Perform deletion
        success_count = 0
        fail_count = 0
        failed_sessions_info = []
        console.print("\n[cyan]Deleting selected sessions...[/cyan]")  # Stdout status
        for full_id in selected_full_ids:
            display_name = id_to_name_map.get(full_id, full_id)
            try:
                session_manager.delete_session(full_id)
                success_count += 1
            except (SessionError, FileNotFoundError) as e:
                fail_count += 1
                failed_sessions_info.append((display_name, str(e)))
            except Exception as e:  # Catch unexpected delete errors
                fail_count += 1
                failed_sessions_info.append(
                    (display_name, f"Unexpected error: {str(e)}")
                )
                console_stderr.print(
                    f"[red]! Unexpected error deleting {display_name}:[/red]"
                )
                traceback.print_exc(file=sys.stderr)

        # Print summary report
        console.print("-" * 20)  # Stdout separator
        if success_count > 0:
            console.print(
                f"[bold green]✅ Successfully deleted {success_count} session(s).[/]"
            )  # Stdout success
        if fail_count > 0:
            # Print failures to stderr for clarity
            console_stderr.print(
                f"[bold yellow]⚠️ Failed to delete {fail_count} session(s):[/]"
            )
            for name, error in failed_sessions_info:
                console_stderr.print(f"  - {name}: {escape(error)}")
        console.print("-" * 20)  # Stdout separator

    except SessionError as e:  # Error listing for deletion
        console_stderr.print(
            f"[bold red]❌ Error listing sessions for deletion: {escape(str(e))}[/bold red]"
        )
        raise typer.Exit(code=1)
    except KeyboardInterrupt:
        console_stderr.print("\nOperation cancelled by user.")
        raise typer.Exit()
    except Exception as e:
        if isinstance(e, typer.Exit):
            raise e  # Avoid double handling typer exits
        console_stderr.print(
            f"[bold red]❌ An unexpected error occurred during delete: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)


# --- Direct Prompt Command Implementation ---


def direct_prompt_logic(
    prompt_text: str,
    file: Optional[Path],
    output_format: str,
    output_file: Optional[Path],
    provider_override: Optional[str],
    model_override: Optional[str],
):
    """
    Core logic for handling the 'prompt' command.

    Initializes dependencies, reads context from stdin or file, constructs
    the final prompt, calls the AI, processes the response, and handles output
    (printing to stdout/stderr or saving to file).

    Args:
        prompt_text: The user's core prompt instruction.
        file: Path to an optional context file.
        output_format: Desired format ('markdown', 'raw', 'json').
        output_file: Optional path to save the output.
        provider_override: Optional provider key.
        model_override: Optional model name.
    """
    # Validate Output Format (using constant)
    if output_format.lower() not in OUTPUT_FORMAT_CHOICES:
        console_stderr.print(
            f"[bold red]❌ Invalid output format: '{output_format}'[/]"
        )
        console_stderr.print(f"Choices: {', '.join(OUTPUT_FORMAT_CHOICES)}")
        raise typer.Exit(code=1)
    output_format = output_format.lower()

    # Initialize AI client (prints status to stderr)
    ai_client = _initialize_dependencies(
        provider_override=provider_override, model_override=model_override
    )

    # --- Input Handling (Stdin / File) ---
    stdin_content: Optional[str] = None
    file_content: Optional[str] = None
    context_source_description: str = ""  # For inclusion in prompt

    # Check Stdin first (non-blocking check)
    if not sys.stdin.isatty():
        console_stderr.print("Reading data from stdin...")
        stdin_content = sys.stdin.read()
        if not stdin_content:
            console_stderr.print("[bold yellow]⚠️ Received empty stdin data.[/]")
            # Continue, maybe the prompt itself is enough
        else:
            try:
                # Check size limit
                stdin_size_bytes = len(stdin_content.encode("utf-8"))
                if stdin_size_bytes > (MAX_UPLOAD_SIZE_KB * 1024):
                    console_stderr.print(
                        f"[bold red]❌ Stdin data too large (>{MAX_UPLOAD_SIZE_KB} KB).[/]"
                    )
                    raise typer.Exit(code=1)
                console_stderr.print(
                    f"Read {stdin_size_bytes / 1024:.1f} KB from stdin."
                )
                context_source_description = "[Data from standard input]"
                # If stdin is used, ignore the --file option
                if file:
                    console_stderr.print(
                        f"[yellow]⚠️ Ignoring --file ('{file.name}') due to stdin data.[/]"
                    )
                    file = None  # Nullify file path
            except Exception as e:  # Catch potential encoding errors etc.
                console_stderr.print(
                    f"[bold red]❌ Error processing stdin data: {escape(str(e))}[/]"
                )
                traceback.print_exc(file=sys.stderr)
                raise typer.Exit(code=1)

    # Read File (only if stdin was not used)
    if file:
        try:
            file_size = file.stat().st_size
            # Validate file size
            if file_size > (MAX_UPLOAD_SIZE_KB * 1024):
                console_stderr.print(
                    f"[bold red]❌ File '{file.name}' too large ({file_size / 1024:.1f} KB > {MAX_UPLOAD_SIZE_KB} KB).[/]"
                )
                raise typer.Exit(code=1)
            if file_size == 0:
                console_stderr.print(f"[bold yellow]⚠️ File '{file.name}' is empty.[/]")
            # Validate file extension (using constant)
            file_ext = file.suffix.lower()
            if ALLOWED_UPLOAD_EXTENSIONS and file_ext not in ALLOWED_UPLOAD_EXTENSIONS:
                allowed_str = ", ".join(ALLOWED_UPLOAD_EXTENSIONS)
                console_stderr.print(
                    f"[bold red]❌ Invalid file type '{file_ext}'. Allowed: {allowed_str}[/]"
                )
                raise typer.Exit(code=1)

            # Read content
            file_content = file.read_text(encoding="utf-8")
            console_stderr.print(
                f"Including file: [green]'{file.name}'[/] ({file_size / 1024:.1f} KB)"
            )
            context_source_description = f"[User provided file: '{escape(file.name)}']"

        except Exception as e:  # Catch stat/read/validation errors
            if isinstance(e, typer.Exit):
                raise e  # Re-raise typer exits
            console_stderr.print(
                f"[bold red]❌ Error processing file '{escape(file.name)}': {escape(str(e))}[/]"
            )
            traceback.print_exc(file=sys.stderr)
            raise typer.Exit(code=1)

    # --- Prompt Construction ---
    context_prefix = ""
    if stdin_content is not None:  # Check against None explicitly
        context_prefix = f"{context_source_description}\n\n--- Input Data Start ---\n{stdin_content}\n--- Input Data End ---\n\n"
    elif file_content is not None:
        context_prefix = f"{context_source_description}\n\n--- File Content Start ---\n{file_content}\n--- File Content End ---\n\n"

    # Add specific instructions based on output format request
    instruction_suffix = ""
    if output_format == "json":
        instruction_suffix = "\n\nRESPONSE FORMATTING INSTRUCTIONS: Ensure your entire response is only a single, valid JSON object or array. Do not include explanations outside the JSON structure."
        console_stderr.print("Requesting JSON output format...")
    elif output_format == "raw":
        instruction_suffix = "\n\nRESPONSE FORMATTING INSTRUCTIONS: Provide only the raw text content requested, without any additional formatting like markdown fences or explanations."
        console_stderr.print("Requesting raw output format...")

    # Combine parts into the final prompt sent to the AI
    final_prompt_to_send = context_prefix + prompt_text + instruction_suffix
    messages = [{"role": "user", "content": final_prompt_to_send}]

    # --- AI Call and Output Handling ---
    try:
        ai_reply = ""
        usage_info = {}
        # Use non-streaming call, show status on stderr
        with console_stderr.status("[yellow]🧠 Thinking...[/]", spinner="dots"):
            ai_reply, usage_info = ai_client.get_completion(messages)

        if not ai_reply:
            console_stderr.print("[italic yellow](Empty response received)[/]")
            # Exit gracefully without error if response is empty
            raise typer.Exit()

        # --- Post-process based on requested format ---
        processed_reply = ai_reply.strip()  # Basic whitespace stripping
        output_content = ai_reply  # Default to original reply for saving/markdown

        if output_format in ["raw", "json"]:
            # Attempt to extract content from markdown code blocks if present
            # Useful if the AI wraps raw/json output in ```
            match = re.match(
                r"^\s*```(?:\w*\s*)?\n?(.*?)\n?```\s*$",
                processed_reply,
                re.DOTALL | re.IGNORECASE,
            )
            if match:
                processed_reply = match.group(1).strip()  # Get content inside ```
            output_content = (
                processed_reply  # Use this processed content for raw/json output
            )

        # --- Handle Output Destination ---
        if output_file:
            try:
                # Prevent overwriting the input file if paths match
                if file and output_file.resolve() == file.resolve():
                    console_stderr.print(
                        f"[bold red]❌ Input file and output file are the same ('{output_file}'). Choose a different output path.[/]"
                    )
                    raise typer.Exit(code=1)

                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(output_content, encoding="utf-8")
                console_stderr.print(
                    f"[bold green]✅ Output saved to:[/bold green] {output_file}"
                )
            except Exception as e:
                console_stderr.print(
                    f"[bold red]❌ Error saving output file: {escape(str(e))}[/bold red]"
                )
                traceback.print_exc(file=sys.stderr)
                raise typer.Exit(code=1)  # Exit if saving failed
        else:
            # Print to standard output
            if output_format == "markdown":
                # Use Rich Console for markdown rendering (respects redirection)
                console.print(Markdown(ai_reply, code_theme=DEFAULT_CODE_THEME))
            elif output_format == "raw":
                # Use standard print for raw output (handles redirection correctly)
                print(processed_reply)
            elif output_format == "json":
                try:
                    # Validate and pretty-print JSON
                    parsed_json = json.loads(processed_reply)
                    print(json.dumps(parsed_json, indent=2))  # Standard print
                except json.JSONDecodeError:
                    # If not valid JSON, print raw but warn on stderr
                    console_stderr.print(
                        "[bold yellow]⚠️ AI response was not valid JSON. Printing raw output.[/]"
                    )
                    print(processed_reply)  # Standard print

        # --- Print Token Usage to stderr ---
        prompt_t = usage_info.get("prompt_tokens", "N/A")
        completion_t = usage_info.get("completion_tokens", "N/A")
        total_t = usage_info.get("total_tokens", "N/A")
        console_stderr.print(
            f"Tokens Used: Prompt=[yellow]{prompt_t}[/], Completion=[yellow]{completion_t}[/], Total=[yellow]{total_t}[/]"
        )

    # --- Error Handling for AI call ---
    except AIClientError as e:
        console_stderr.print(f"[bold red]\n❌ AI Error: {escape(str(e))}[/bold red]")
        raise typer.Exit(code=1)
    except typer.Exit as e:  # Re-raise exits from validation etc.
        raise e
    except Exception as e:
        console_stderr.print(
            f"[bold red]\n❌ Unexpected Error: {escape(str(e))}[/bold red]"
        )
        traceback.print_exc(file=sys.stderr)
        raise typer.Exit(code=1)
