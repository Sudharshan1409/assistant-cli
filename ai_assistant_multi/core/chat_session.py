# core/chat_session.py
"""
Contains the ChatSession class responsible for managing the interactive chat loop,
handling user commands within a session, processing file uploads, and interacting
with the AI client.
"""

import os
import re
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Rich components for UI
from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.table import Table
from rich.text import Text

# Import constants
from ..constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    DEFAULT_CODE_THEME,
    EDITOR_ENV_VAR,
    EDITOR_PLACEHOLDER_COMMENT,
    MAX_FILENAMES_IN_PROMPT,
    MAX_UPLOAD_SIZE_KB,
)

# Core utilities and base classes
from ..utils.base_client import AIClientError, BaseAIClient
from ..utils.session_manager import SessionError, SessionManager


class ChatSession:
    """
    Represents and manages an active interactive chat session.

    Handles message history, user commands (like /help, /upload), file context,
    interaction with the AI model (via the provided client), session naming,
    and persistence via the SessionManager.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        ai_client: BaseAIClient,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
    ):
        """
        Initializes a ChatSession instance.

        Args:
            session_manager: An instance of SessionManager for persistence.
            ai_client: An instance of a BaseAIClient subclass for AI interaction.
            session_id: The full ID (name_uuid) if resuming an existing session.
            session_name: The desired name if starting a new named session.
        """
        self.session_manager = session_manager
        self.ai_client = ai_client
        self.messages: List[Dict[str, str]] = []  # In-memory message history
        self.session_id: Optional[str] = (
            session_id  # Will be set if resuming or after naming
        )
        self.console = Console()  # Rich console for output

        # State for pending file uploads within the session
        self._pending_files: List[Tuple[Path, str]] = (
            []
        )  # Stores (absolute_path, content)
        self._pending_file_paths: Set[str] = (
            set()
        )  # Stores absolute_path_str for quick duplicate checks

        # In-memory token counts for the current session instance
        # These are estimates, especially when resuming sessions without saved token data.
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        # self.session_total_tokens is calculated in /usage

        # Determine session ID and initial state
        self._needs_naming: bool = False
        if session_id:
            self.session_id = session_id  # Resuming session
        elif session_name:
            # Generate ID for a new, named session
            self.session_id = self.session_manager._generate_full_session_id(
                session_name
            )
        else:
            # New, unnamed session - will be named after first prompt
            self._needs_naming = True

    @property
    def display_name(self) -> str:
        """Returns the user-friendly display name derived from the session ID."""
        if self.session_id:
            # Extract the name part before the '_uuid' suffix
            name, _ = self.session_manager._split_session_id(self.session_id)
            return name
        elif self._needs_naming:
            return "[Pending Name]"  # Placeholder until named
        else:
            # Should not happen if logic is correct, but fallback
            return "[Unnamed Session]"

    def _get_relative_path_str(self, file_path: Path) -> str:
        """
        Calculates the relative path of a file from the current working directory.

        Args:
            file_path: An absolute Path object.

        Returns:
            The relative path as a string, or the absolute path if not under CWD.
        """
        try:
            # Ensure paths are absolute and resolved before comparison
            return str(file_path.resolve().relative_to(Path.cwd().resolve()))
        except ValueError:
            # File is not relative to CWD, return absolute path
            return str(file_path.resolve())
        except Exception:
            # Fallback for any other errors
            return str(file_path.resolve())

    def _display_history(self, limit: Optional[int] = None):
        """Renders and displays the session's message history."""
        if not self.messages:
            self.console.print("[yellow]Session history is empty.[/yellow]")
            return

        self.console.print(
            f"\n[bold underline]History for Session: {self.display_name}[/bold underline]"
        )
        messages_to_show = self.messages[-limit:] if limit else self.messages

        for msg in messages_to_show:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            role_color = "cyan" if role == "user" else "green"

            # Print role header
            self.console.print(
                f"[bold {role_color}]{role.capitalize()}[/bold {role_color}]: ", end=""
            )

            # Render content based on role
            if role == "user":
                # User messages might contain file context, print escaped
                self.console.print(escape(content))
            else:
                # Render AI responses as Markdown
                md = Markdown(content, code_theme=DEFAULT_CODE_THEME)
                self.console.print(md)

        self.console.print("-" * 20)  # Separator

    def _show_help(self):
        """Displays available in-chat commands using an aligned table."""
        self.console.print("\n[bold green]Available Commands:[/bold green]")

        # Command definitions: (styled_command, description)
        help_items = [
            (
                "[bold blue]/rename <new_name>[/bold blue]",
                f"Rename the current session '{self.display_name}'",
            ),
            ("[bold blue]/history[/bold blue]", "Show current session message history"),
            (
                "[bold blue]/clear[/bold blue]",
                "Clear current session message history (cannot be undone)",
            ),
            (
                "[bold blue]/upload [path][/bold blue]",
                "Load a file (interactive if path omitted)",
            ),
            (
                "[bold blue]/edit[/bold blue]",
                f"Open external editor (${EDITOR_ENV_VAR}) for multi-line input",
            ),
            (
                "[bold blue]/status[/bold blue]",
                "Show pending files (relative paths) to be uploaded",
            ),
            (
                "[bold blue]/clearfiles[/bold blue]",
                "Clear all pending files without sending",
            ),
            (
                "[bold blue]/usage[/bold blue]",
                "Show token usage estimate for this session",
            ),
            ("[bold blue]/help[/bold blue]", "Show this help message"),
            ("[bold blue]/exit | /quit[/bold blue]", "End the chat session"),
        ]

        # Use Rich Table for automatic alignment
        table = Table(show_header=False, box=None, padding=(0, 2), show_edge=False)
        table.add_column(style="none", no_wrap=True)  # Command column
        table.add_column()  # Description column

        for styled_cmd, description in help_items:
            table.add_row(styled_cmd, f"- {description}")

        self.console.print(table)

    def load_or_create(self):
        """
        Loads session data (messages) if session_id exists, otherwise creates
        a new session file. Handles the initial state for new/resumed sessions.
        """
        if self._needs_naming:
            # This is a new, unnamed session. Initialize empty state.
            self.console.print(
                "[bold green]✨ Starting new chat. Session will be named after your first message.[/bold green]"
            )
            self.messages = []
            self.session_prompt_tokens = 0
            self.session_completion_tokens = 0
            return  # Don't interact with file system yet

        if not self.session_id:
            # This case should ideally be prevented by the constructor logic
            raise SessionError(
                "Internal Error: Session ID is unexpectedly missing when trying to load/create."
            )

        try:
            # Attempt to load messages for the existing session ID
            self.messages = self.session_manager.load_messages(self.session_id)
            # Reset token counts on load - we don't store/retrieve them in this version
            self.session_prompt_tokens = 0
            self.session_completion_tokens = 0
            self.console.print(
                f"[bold green]🔄 Resuming session: {self.display_name} (ID: {self.session_id})[/bold green]"
            )
            self._display_history()  # Show loaded history

        except FileNotFoundError:
            # Session file doesn't exist, create a new one for this ID
            try:
                self.session_manager.create(
                    self.session_id
                )  # Creates empty message list file
                self.messages = []  # Ensure local messages are empty
                self.session_prompt_tokens = 0  # Reset tokens
                self.session_completion_tokens = 0
                self.console.print(
                    f"[bold green]✨ Started new session: {self.display_name} (ID: {self.session_id})[/bold green]"
                )
            except (SessionError, FileExistsError) as e:
                # Handle potential race condition or permission issues
                self.console.print(
                    f"[bold red]❌ Error creating session file '{self.session_id}': {escape(str(e))}[/bold red]"
                )
                raise  # Propagate error

        except SessionError as e:
            # Handle errors during loading (e.g., invalid JSON)
            self.console.print(
                f"[bold red]❌ Error loading session '{self.session_id}': {escape(str(e))}[/bold red]"
            )
            # Attempt to start with empty state? Or just fail? Let's fail.
            raise  # Propagate error

    def _add_message(self, role: str, content: str):
        """Adds a message to the local history and persists it to the file."""
        if not self.session_id:
            self.console.print(
                "[bold yellow]⚠️ Cannot save message: Session ID not yet determined.[/bold yellow]"
            )
            return  # Don't modify local state if we can't save

        self.messages.append({"role": role, "content": content})
        try:
            # Append and save immediately using the manager
            self.session_manager.append_message(self.session_id, role, content)
        except SessionError as e:
            self.console.print(
                f"[bold red]❌ Error saving message: {escape(str(e))}[/bold red]"
            )
            # If saving failed, remove the message we just added locally to maintain consistency
            if (
                self.messages
                and self.messages[-1]["role"] == role
                and self.messages[-1]["content"] == content
            ):
                try:
                    self.messages.pop()
                except IndexError:
                    pass  # Should not happen, but safety check
            self.console.print(
                "[bold yellow]⚠️ Message added in memory but failed to save to disk.[/bold yellow]"
            )
            # Potentially raise error here? For now, just warn.

    def _generate_and_set_session_name(self, first_user_message: str) -> bool:
        """
        Generates a session name using the AI based on the first user prompt,
        creates the session file, and sets the internal session ID.

        Args:
            first_user_message: The content of the user's first message.

        Returns:
            True if naming and session creation were successful, False otherwise.
        """
        ai_reply_name = None
        try:
            # Prompt to generate a concise name
            prompt_text = (
                "Based on the following user message, generate a concise, 2-4 word title "
                "suitable for a filename (use lowercase words, separated by hyphens). "
                "Example: 'analyze-stock-data'. Do not include any explanation, just the title.\n\n"
                f'User Message: "{escape(first_user_message[:200])}"'  # Limit length sent for naming
            )
            with self.console.status(
                "[yellow]💬 Generating session name...[/]", spinner="dots"
            ):
                # Use non-streaming call, ignore token usage for simplicity now
                ai_reply_name, _ = self.ai_client.get_completion(
                    messages=[{"role": "user", "content": prompt_text}],
                    temperature=0.3,  # Low temp for more predictable naming
                )

            # Sanitize the generated name
            if ai_reply_name:
                ai_reply_name = ai_reply_name.strip().strip(
                    "'\"`"
                )  # Remove quotes/ticks
                # Replace whitespace with hyphens, lowercase
                sanitized_name = re.sub(r"\s+", "-", ai_reply_name.lower())
                # Remove invalid filename characters (allow letters, numbers, hyphen, underscore)
                sanitized_name = re.sub(r"[^\w\-]+", "", sanitized_name)
                # Limit length and remove leading/trailing hyphens
                sanitized_name = "-".join(sanitized_name.split("-")[:4]).strip("-")[
                    :50
                ]  # Example: max 4 words, 50 chars
            else:
                sanitized_name = ""

            # Fallback name if sanitization results in empty string
            if not sanitized_name:
                sanitized_name = "chat"

            # Generate the unique ID and create the session file
            temp_session_id = self.session_manager._generate_full_session_id(
                sanitized_name
            )
            self.session_manager.create(
                temp_session_id
            )  # Creates empty message list file

            # Update internal state
            self.session_id = temp_session_id
            self._needs_naming = False
            self.console.print(
                f"[bold green]✅ Session automatically named: {self.display_name} (ID: {self.session_id})[/bold green]"
            )
            return True

        except AIClientError as e:
            self.console.print(
                f"[bold red]\n❌ AI Error generating name: {escape(str(e))}[/bold red]"
            )
        except (SessionError, FileExistsError) as e:
            self.console.print(
                f"[bold red]\n❌ Error creating session file during naming: {escape(str(e))}[/bold red]"
            )
        except Exception as e:
            self.console.print(
                f"[bold red]\n❌ Unexpected error during naming: {escape(str(e))}[/bold red]"
            )
            traceback.print_exc(file=sys.stderr)

        # Naming failed
        self.console.print(
            "[bold yellow]⚠️ Session naming failed. Please try starting your chat again or use --name.[/bold yellow]"
        )
        return False

    def _handle_rename(self, user_input: str):
        """Renames the current session file."""
        new_display_name = user_input[len("/rename ") :].strip()
        if not new_display_name:
            self.console.print(
                "[bold yellow]⚠️ Please provide a new name: /rename <new_name>[/bold yellow]"
            )
            return
        if not self.session_id:
            self.console.print(
                "[bold red]❌ Cannot rename: Session ID not yet determined.[/bold red]"
            )
            return

        old_full_id = self.session_id
        old_display_name = self.display_name
        try:
            # SessionManager handles the file renaming logic
            new_full_id = self.session_manager.rename(old_full_id, new_display_name)

            if new_full_id and new_full_id != old_full_id:
                self.session_id = new_full_id  # Update the internal ID
                self.console.print(
                    f"[bold green]✅ Session renamed from '{old_display_name}' to '{self.display_name}'[/bold green]"
                )
            elif new_full_id is None or new_full_id == old_full_id:
                # Handle case where name results in same ID (no change) or rename failed silently
                self.console.print(
                    "[yellow]New name is the same or could not be applied. No changes made.[/yellow]"
                )

        except (FileNotFoundError, FileExistsError, SessionError, ValueError) as e:
            # Catch specific errors from the rename operation
            self.console.print(
                f"[bold red]❌ Rename failed: {escape(str(e))}[/bold red]"
            )
            # Ensure internal session ID remains the old one if rename failed
            self.session_id = old_full_id
        except Exception as e:
            self.console.print(
                f"[bold red]❌ Unexpected error during rename: {escape(str(e))}[/bold red]"
            )
            traceback.print_exc(file=sys.stderr)
            self.session_id = old_full_id  # Revert internal ID on unexpected error

    def _handle_history(self):
        """Handles the /history command."""
        self._display_history()

    def _handle_clear(self):
        """Handles the /clear command, confirming before clearing history."""
        if not self.session_id:
            self.console.print(
                "[bold red]❌ Cannot clear history: Session ID not yet determined.[/bold red]"
            )
            return

        # Confirm with the user
        confirm = questionary.confirm(
            f"❓ Are you sure you want to clear all history for session '{self.display_name}'? This cannot be undone.",
            default=False,
        ).ask()

        if confirm:
            self.messages = []  # Clear in-memory messages
            # Reset token estimates (though not reliably saved/loaded in this version)
            self.session_prompt_tokens = 0
            self.session_completion_tokens = 0
            try:
                # Save the empty message list to the file
                self.session_manager.save_messages(self.session_id, [])
                self.console.print(
                    f"[bold green]✅ History for session '{self.display_name}' cleared.[/bold green]"
                )
            except SessionError as e:
                # Handle error saving the cleared state
                self.console.print(
                    f"[bold red]❌ Error saving cleared session history: {escape(str(e))}[/bold red]"
                )
                self.console.print(
                    "[bold yellow]⚠️ History cleared in memory, but failed to update the file.[/bold yellow]"
                )
        else:
            self.console.print("Clear operation cancelled.")

    def _handle_upload(self, user_input: str):
        """
        Handles the /upload command.

        Validates the file path (or uses fzf/fd if available), checks size and extension,
        reads the content, and adds it to the pending files list.
        """
        parts = user_input.split(maxsplit=1)
        file_path_str: Optional[str] = None
        selected_path_obj: Optional[Path] = None

        # --- Path Determination (Manual or Interactive) ---
        if len(parts) > 1:
            # Path provided directly
            file_path_str = parts[1].strip()
            try:
                selected_path_obj = Path(file_path_str).expanduser().resolve()
            except Exception as e:
                self.console.print(
                    f"[bold red]❌ Invalid path provided: {escape(str(e))}[/bold red]"
                )
                return
        else:
            # No path provided, attempt interactive selection
            fzf_path = shutil.which("fzf")
            fd_path = shutil.which("fd")

            if fzf_path and fd_path:
                self.console.print(
                    "[cyan]Launching interactive file picker (requires 'fzf' and 'fd')...[/cyan]"
                )
                # Define preview command (uses bat/eza if available)
                preview_cmd_part = "bat -n --color=always --line-range :500 {}"  # Default preview using bat
                if shutil.which("eza"):
                    preview_cmd_part = (
                        "eza --tree --color=always {} | head -200"  # Use eza for dirs
                    )
                elif not shutil.which("bat"):
                    preview_cmd_part = "head -50 {}"  # Fallback preview

                preview_command = f"if [ -d {{}} ]; then {preview_cmd_part.format('{}')}; elif [ -f {{}} ]; then {preview_cmd_part.format('{}')}; else echo 'Cannot preview'; fi"

                # fd command to find files in CWD, excluding .git
                fd_command = [
                    fd_path,
                    "--hidden",
                    "--strip-cwd-prefix",
                    "--exclude",
                    ".git",
                    "--type",
                    "file",
                    ".",
                ]
                try:
                    # Get file list from fd
                    fd_process = subprocess.run(
                        fd_command,
                        capture_output=True,
                        text=True,
                        check=True,
                        cwd=Path.cwd(),
                    )
                    file_list = fd_process.stdout
                    if not file_list:
                        self.console.print(
                            "[yellow]No files found by 'fd' in the current directory.[/yellow]"
                        )
                        return

                    # Pipe file list to fzf for selection
                    fzf_process = subprocess.run(
                        [fzf_path, "--preview", preview_command],
                        input=file_list,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                    if fzf_process.returncode == 0 and fzf_process.stdout:
                        # fzf returns path relative to where fd ran (CWD)
                        selected_relative_path_str = fzf_process.stdout.strip()
                        # Resolve to absolute path
                        selected_path_obj = (
                            Path.cwd().joinpath(selected_relative_path_str).resolve()
                        )
                        file_path_str = str(
                            selected_path_obj
                        )  # For potential error messages
                        self.console.print(
                            f"[cyan]Selected: {selected_relative_path_str}[/cyan]"
                        )
                    elif fzf_process.returncode == 130:  # User cancelled fzf
                        self.console.print("File selection cancelled.")
                        return
                    else:  # Other fzf error
                        error_msg = (
                            fzf_process.stderr.strip()
                            or f"fzf exited with code {fzf_process.returncode}"
                        )
                        self.console.print(
                            f"[bold red]❌ File picker error (fzf):[/bold red] {error_msg}"
                        )
                        return

                except subprocess.CalledProcessError as e:
                    # Error running fd
                    self.console.print(
                        f"[bold red]❌ File picker error (fd): {e}[/]\n[dim]{e.stderr}[/dim]"
                    )
                    return
                except Exception as e:
                    # Unexpected error during picker process
                    self.console.print(
                        f"[bold red]❌ Error running file picker: {escape(str(e))}[/bold red]"
                    )
                    traceback.print_exc(file=sys.stderr)
                    return
            else:
                # fzf or fd not found
                missing = [
                    cmd
                    for cmd, path in [("'fzf'", fzf_path), ("'fd'", fd_path)]
                    if not path
                ]
                self.console.print(
                    f"[bold red]❌ Interactive picker requires: {', '.join(missing)}.[/]"
                )
                self.console.print(
                    "[yellow]💡 Please provide the file path directly: /upload <path/to/file>[/]"
                )
                return

        # --- File Validation and Processing ---
        if selected_path_obj:
            try:
                # Use absolute path string for duplicate check
                resolved_path_str = str(selected_path_obj)
                if resolved_path_str in self._pending_file_paths:
                    self.console.print(
                        f"[yellow]⚠️ File '{self._get_relative_path_str(selected_path_obj)}' is already staged.[/]"
                    )
                    return

                # Perform validations
                if not selected_path_obj.exists():
                    raise FileNotFoundError("File not found.")
                if not selected_path_obj.is_file():
                    raise ValueError("Path is not a file.")

                # Check extension
                file_ext = selected_path_obj.suffix.lower()
                if (
                    ALLOWED_UPLOAD_EXTENSIONS
                    and file_ext not in ALLOWED_UPLOAD_EXTENSIONS
                ):
                    allowed_str = ", ".join(ALLOWED_UPLOAD_EXTENSIONS)
                    raise ValueError(
                        f"Invalid file type '{file_ext}'. Allowed: {allowed_str}"
                    )

                # Check size
                file_size = selected_path_obj.stat().st_size
                max_size_bytes = MAX_UPLOAD_SIZE_KB * 1024
                if file_size > max_size_bytes:
                    raise ValueError(
                        f"File too large ({file_size / 1024:.1f} KB > {MAX_UPLOAD_SIZE_KB} KB)."
                    )
                if file_size == 0:
                    self.console.print(
                        f"[bold yellow]⚠️ File '{selected_path_obj.name}' is empty.[/]"
                    )

                # Read content
                content = selected_path_obj.read_text(encoding="utf-8")

                # Add to pending lists
                self._pending_files.append(
                    (selected_path_obj, content)
                )  # Store (abs_path, content)
                self._pending_file_paths.add(
                    resolved_path_str
                )  # Store abs_path_str for checking

                # Confirmation message
                file_size_kb = file_size / 1024
                display_path = self._get_relative_path_str(selected_path_obj)
                self.console.print(
                    f"[bold green]✅ File '{escape(display_path)}' staged ({file_size_kb:.1f} KB).[/]"
                )
                self.console.print(
                    "[dim]   It will be included in the context of the next prompt.[/dim]"
                )

            except (ValueError, FileNotFoundError, UnicodeDecodeError, IOError) as e:
                # Handle specific validation/read errors
                self.console.print(
                    f"[bold red]❌ Error processing file '{escape(file_path_str or 'selected file')}': {escape(str(e))}[/bold red]"
                )
            except Exception as e:
                # Catch unexpected errors during validation/reading
                if isinstance(e, typer.Exit):
                    raise e  # Avoid double handling
                self.console.print(
                    f"[bold red]❌ Unexpected error processing file '{escape(file_path_str or 'selected file')}': {escape(str(e))}[/bold red]"
                )
                traceback.print_exc(file=sys.stderr)

    def _handle_edit(self) -> Optional[str]:
        """Opens the configured external editor ($EDITOR) for multi-line input."""
        editor = os.getenv(EDITOR_ENV_VAR)
        if not editor:
            self.console.print(
                f"[bold red]❌ ${EDITOR_ENV_VAR} environment variable not set.[/bold red]"
            )
            self.console.print(
                "[yellow]   Set it to your preferred editor (e.g., vim, nano, code).[/]"
            )
            return None

        temp_file_path: Optional[Path] = None
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(
                mode="w+t", suffix=".md", delete=False, encoding="utf-8"
            ) as tf:
                temp_file_path = Path(tf.name)
                tf.write(EDITOR_PLACEHOLDER_COMMENT)  # Add placeholder text
                tf.flush()  # Ensure content is written before editor opens

            self.console.print(
                f"[cyan]Opening editor ('{editor}') for input. Save and exit when done.[/cyan]"
            )
            # Run the editor process
            editor_cmd = [editor, str(temp_file_path)]
            process = subprocess.run(
                editor_cmd
            )  # Let editor handle stdin/stdout/stderr

            if process.returncode != 0:
                self.console.print(
                    f"[bold yellow]⚠️ Editor exited with status {process.returncode}. Input might not be saved.[/bold yellow]"
                )

            # Read content back from the temporary file if it exists
            if temp_file_path and temp_file_path.exists():
                content = temp_file_path.read_text(encoding="utf-8").strip()
                # Remove the placeholder comment if it's still there
                if content.startswith(EDITOR_PLACEHOLDER_COMMENT.strip()):
                    lines = content.split("\n", 1)
                    content = lines[1].strip() if len(lines) > 1 else ""
                return content  # Return the edited content
            else:
                self.console.print(
                    "[yellow]Edit cancelled or temporary file lost.[/yellow]"
                )
                return None
        except FileNotFoundError:
            # Editor command itself not found
            self.console.print(
                f"[bold red]❌ Editor command not found: '{editor}'[/bold red]"
            )
            self.console.print(
                "[yellow]   Ensure $EDITOR is set correctly and the editor is in your system's PATH.[/]"
            )
            return None
        except Exception as e:
            # Handle unexpected errors during the editor process
            self.console.print(
                f"[bold red]❌ Error during editor process: {escape(str(e))}[/bold red]"
            )
            traceback.print_exc(file=sys.stderr)
            return None
        finally:
            # Ensure temporary file cleanup
            if temp_file_path and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                except OSError:
                    # Non-critical error, just warn if cleanup fails
                    self.console.print(
                        f"[yellow]⚠️ Could not delete temporary editor file {temp_file_path}[/]"
                    )

    def _handle_status(self):
        """Displays the list of currently pending files using relative paths."""
        if not self._pending_files:
            self.console.print("[yellow]No files pending for the next prompt.[/yellow]")
        else:
            self.console.print(
                f"[bold cyan]Pending files ({len(self._pending_files)}):[/bold cyan]"
            )
            total_kb = 0
            for i, (fpath_obj, content) in enumerate(self._pending_files):
                rel_path_str = self._get_relative_path_str(fpath_obj)
                content_kb = len(content.encode("utf-8")) / 1024
                total_kb += content_kb
                self.console.print(
                    f"  {i+1}. {escape(rel_path_str)} ({content_kb:.1f} KB)"
                )
            self.console.print(f"[dim]Total size: {total_kb:.1f} KB[/dim]")
            self.console.print(
                "[dim]Use /clearfiles to remove all pending files.[/dim]"
            )

    def _handle_clear_files(self):
        """Clears the list and set of pending files."""
        if not self._pending_files:
            self.console.print("[yellow]No pending files to clear.[/yellow]")
        else:
            num_cleared = len(self._pending_files)
            self._pending_files = []
            self._pending_file_paths.clear()
            self.console.print(
                f"[bold green]✅ Cleared {num_cleared} pending file(s).[/]"
            )

    def _handle_usage(self):
        """Displays the estimated token usage for the current session instance."""
        self.console.print(
            "\n[bold cyan]Token Usage Estimate (Current Session Instance):[/bold cyan]"
        )
        # Recalculate total on the fly
        total = self.session_prompt_tokens + self.session_completion_tokens
        self.console.print(
            f"  Prompt Tokens Accumulated:     {self.session_prompt_tokens}"
        )
        self.console.print(
            f"  Completion Tokens Accumulated: {self.session_completion_tokens}"
        )
        self.console.print(f"  Estimated Total:               {total}")
        self.console.print(
            "[dim]Note: This is an in-memory estimate and may reset if the session is resumed.[/dim]"
        )

    def run_interaction_loop(self):
        """Runs the main interactive input loop (non-streaming)."""
        if not self._needs_naming:
            self.console.print(
                "[bold blue]Type '/help' for commands, '/exit' or '/quit' to end.[/bold blue]"
            )

        while True:
            try:
                # --- Display Prompt Line ---
                self.console.print(
                    f"\n[bold cyan]{self.display_name}[/bold cyan]", end=""
                )
                # Show pending files (relative paths)
                if self._pending_files:
                    display_paths = [
                        self._get_relative_path_str(fpath)
                        for fpath, _ in self._pending_files
                    ]
                    escaped_paths = [escape(p) for p in display_paths]
                    limited_paths = escaped_paths[:MAX_FILENAMES_IN_PROMPT]
                    files_str = ", ".join(limited_paths)
                    if len(escaped_paths) > MAX_FILENAMES_IN_PROMPT:
                        files_str += f", ... ({len(escaped_paths)} total)"
                    file_info = Text(f" (Files: {files_str})", style="italic yellow")
                    self.console.print(" ", file_info, end="")
                self.console.print(" [bold cyan]> You[/bold cyan]: ", end="")
                # --- End Prompt Line ---

                # Get user input
                user_input = input().strip()

                # --- Handle Exit ---
                if user_input.lower() in ["/exit", "/quit"]:
                    self.console.print(
                        "[bold magenta]👋 Exiting session.[/bold magenta]"
                    )
                    break  # Exit loop

                # --- Handle Commands ---
                is_command = user_input.startswith("/")
                edited_content: Optional[str] = None
                if is_command:
                    if user_input.lower() == "/usage":
                        self._handle_usage()
                        continue
                    elif user_input.lower() == "/help":
                        self._show_help()
                        continue
                    elif user_input.lower() == "/edit":
                        edited_content = self._handle_edit()
                        if edited_content is None:
                            continue  # Edit cancelled or failed
                        user_input = edited_content  # Use edited content as prompt
                        is_command = False  # Process as regular message now
                    elif user_input.lower().startswith("/upload"):
                        self._handle_upload(user_input)
                        continue
                    elif user_input.lower() == "/status":
                        self._handle_status()
                        continue
                    elif user_input.lower() == "/clearfiles":
                        self._handle_clear_files()
                        continue
                    # Commands requiring a session ID
                    elif self.session_id:
                        if user_input.lower().startswith("/rename"):
                            self._handle_rename(user_input)
                            continue
                        elif user_input.lower() == "/history":
                            self._handle_history()
                            continue
                        elif user_input.lower() == "/clear":
                            self._handle_clear()
                            continue
                        else:
                            self.console.print(
                                f"[yellow]⚠️ Unknown command: {user_input}[/]"
                            )
                            continue
                    else:  # Command requires ID, but session not named yet
                        self.console.print(
                            "[yellow]⚠️ Command requires session name. Please send a message first.[/]"
                        )
                        continue
                # --- End Command Handling ---

                # --- Process Regular Message ---
                if user_input and not is_command:
                    # Handle automatic naming if needed
                    if self._needs_naming:
                        if not self._generate_and_set_session_name(user_input):
                            continue  # Naming failed, prompt again

                    # This check should always pass if naming succeeded or session was loaded
                    if not self.session_id:
                        self.console.print(
                            "[bold red]❌ Internal Error: Session ID missing before sending message.[/]"
                        )
                        continue

                    # --- Build Final Prompt Content ---
                    final_user_content = user_input
                    # Prepend context from pending files if any
                    if self._pending_files:
                        context_prefix = ""
                        for i, (fpath_obj, fcontent) in enumerate(self._pending_files):
                            rel_path_str = self._get_relative_path_str(fpath_obj)
                            escaped_rel_path = escape(rel_path_str)
                            context_prefix += (
                                f"[User uploaded file {i+1}: '{escaped_rel_path}']\n"
                                f"--- File Content Start ({escaped_rel_path}) ---\n"
                                f"{fcontent}\n"
                                f"--- File Content End ({escaped_rel_path}) ---\n\n"
                            )
                        final_user_content = context_prefix + user_input
                        # Clear pending files *after* successfully building context
                        self._pending_files = []
                        self._pending_file_paths.clear()
                    # --- End Building Prompt ---

                    # Add user message to history (persists immediately)
                    self._add_message("user", final_user_content)

                    # --- Call AI (Non-Streaming) ---
                    try:
                        self.console.print(
                            f"\n[bold green]{self.display_name} > AI[/bold green]: ",
                            end="",
                        )
                        ai_reply = ""
                        usage_info = {}
                        with self.console.status(
                            "[yellow]🧠 Thinking...[/]", spinner="dots"
                        ):
                            ai_reply, usage_info = self.ai_client.get_completion(
                                self.messages
                            )

                        # Accumulate token estimates for /usage
                        prompt_tokens = usage_info.get("prompt_tokens", 0)
                        completion_tokens = usage_info.get("completion_tokens", 0)
                        self.session_prompt_tokens += prompt_tokens
                        self.session_completion_tokens += completion_tokens

                        # Process and display response
                        if ai_reply:
                            md = Markdown(ai_reply, code_theme=DEFAULT_CODE_THEME)
                            self.console.print(md)
                            # Add assistant message to history (persists immediately)
                            self._add_message("assistant", ai_reply)
                        else:
                            self.console.print(
                                "[italic yellow](Empty response received)[/]"
                            )

                        # Display per-turn token usage
                        prompt_t_str = (
                            str(prompt_tokens) if prompt_tokens is not None else "N/A"
                        )
                        comp_t_str = (
                            str(completion_tokens)
                            if completion_tokens is not None
                            else "N/A"
                        )
                        total_t_str = str(
                            prompt_tokens + completion_tokens
                        )  # Calculate simple sum
                        self.console.print(
                            f"[dim]Tokens: Prompt={prompt_t_str}, Completion={comp_t_str}, Total={total_t_str}[/]"
                        )

                    except AIClientError as e:
                        self.console.print(
                            f"[bold red]\n❌ AI Error: {escape(str(e))}[/bold red]"
                        )
                        # Attempt to remove the last user message from history if AI call failed
                        if self.messages and self.messages[-1]["role"] == "user":
                            try:
                                failed_user_message = self.messages.pop()
                                # Resave the history without the failed message
                                self.session_manager.save_messages(
                                    self.session_id, self.messages
                                )
                                self.console.print(
                                    "[yellow]ⓘ Last user message removed from history due to AI error.[/yellow]"
                                )
                            except SessionError:
                                self.console.print(
                                    "[bold red]⚠️ Failed to revert last user message after AI error.[/bold red]"
                                )
                                # Put message back in memory if save failed?
                                self.messages.append(failed_user_message)
                        continue  # Continue to next prompt
                    except Exception as e:
                        # Catch unexpected errors during AI call
                        self.console.print(
                            f"[bold red]\n❌ Unexpected Error during AI call: {escape(str(e))}[/bold red]"
                        )
                        traceback.print_exc(file=sys.stderr)
                        continue  # Continue to next prompt
                    # --- End AI Call ---

            # --- Loop Exception Handling ---
            except EOFError:  # User pressed Ctrl+D
                # Clear pending files on exit
                if self._pending_files:
                    self._pending_files = []
                    self._pending_file_paths.clear()
                    self.console.print(
                        "[yellow]\n⚠️ Pending file(s) cleared due to EOF.[/yellow]"
                    )
                self.console.print(
                    "\n[bold magenta]👋 Exiting session (EOF detected).[/bold magenta]"
                )
                break
            except KeyboardInterrupt:  # User pressed Ctrl+C
                if self._pending_files:
                    self._pending_files = []
                    self._pending_file_paths.clear()
                    self.console.print(
                        "[yellow]\n⚠️ Pending file(s) cleared due to interrupt.[/yellow]"
                    )
                self.console.print(
                    "\n[bold magenta]👋 Exiting session (Interrupt detected).[/bold magenta]"
                )
                break
            except Exception as e:  # Catch-all for unexpected loop errors
                self.console.print(
                    f"[bold red]\n❌ Unexpected Error in interaction loop: {escape(str(e))}[/bold red]"
                )
                traceback.print_exc(file=sys.stderr)
                # Clear pending files on unexpected error for safety
                if self._pending_files:
                    self._pending_files = []
                    self._pending_file_paths.clear()
                    self.console.print(
                        "[yellow]\n⚠️ Pending file(s) cleared due to unexpected error.[/yellow]"
                    )
                break  # Exit loop
