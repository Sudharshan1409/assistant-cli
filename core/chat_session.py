# core/chat_session.py
import os
import re
import shutil
import subprocess
import tempfile
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple  # <-- Import Set

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape
from rich.text import Text

from utils.ai_client import AIClient, AIClientError

# Import the manager/client classes
from utils.session_manager import SessionError, SessionManager


class ChatSession:
    """Represents and manages an active chat session interaction."""

    CODE_THEME = "native"
    MAX_UPLOAD_SIZE_KB = 50  # Max size for *each* uploaded file
    ALLOWED_EXTENSIONS = {
        ".txt",
        ".md",
        ".py",
        ".json",
        ".csv",
        ".html",
        ".css",
        ".js",
        ".yaml",
        ".yml",
        ".sh",
        ".xml",
        ".log",
        ".ini",
        ".cfg",
        ".toml",
    }
    # Max filenames to show directly in prompt
    MAX_FILENAMES_IN_PROMPT = 3

    def __init__(
        self,
        session_manager: SessionManager,
        ai_client: AIClient,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
    ):
        self.session_manager = session_manager
        self.ai_client = ai_client
        self.messages: List[Dict[str, str]] = []
        self._needs_naming: bool = False
        self.session_id: Optional[str] = None
        self.console = Console()
        self._pending_files: List[Tuple[str, str]] = []
        # Add set to track full paths
        self._pending_file_paths: Set[str] = set()

        if session_id:
            self.session_id = session_id
        elif session_name:
            self.session_id = self.session_manager._generate_full_session_id(
                session_name
            )
        else:
            self._needs_naming = True

    @property
    def display_name(self) -> str:
        """Returns the user-friendly display name of the session."""
        if self.session_id:
            name, _ = self.session_manager._split_session_id(self.session_id)
            return name
        elif self._needs_naming:
            return "[Pending Name]"
        else:
            return "[Unnamed Session]"

    def _display_history(self, limit: Optional[int] = None):
        """Displays the current message history using Markdown rendering."""
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
            self.console.print(
                f"[bold {role_color}]{role.capitalize()}[/bold {role_color}]: ", end=""
            )
            # Display user input plainly in history (escaped)
            if role == "user":
                self.console.print(escape(content))
            else:
                # Render AI content as Markdown
                md = Markdown(
                    content,
                    code_theme=self.CODE_THEME,
                    inline_code_theme=self.CODE_THEME,
                )
                self.console.print(md)
        self.console.print("-" * 20)

    def _show_help(self):
        """Displays available in-chat commands."""
        self.console.print("\n[bold green]Available Commands:[/bold green]")
        self.console.print(
            f"[bold blue]/rename <new_name>[/bold blue]   - Rename the current session '{self.display_name}'"
        )
        self.console.print(
            "[bold blue]/history[/bold blue]            - Show current session message history"
        )
        self.console.print(
            "[bold blue]/clear[/bold blue]              - Clear current session message history (cannot be undone)"
        )
        self.console.print(
            "[bold blue]/upload [file_path][/bold blue] - Load a file (interactive if path omitted and 'fzf' installed)"
        )
        self.console.print(
            "[bold blue]/edit[/bold blue]               - Open external editor ($EDITOR) for multi-line input"
        )
        self.console.print(
            "[bold blue]/status[/bold blue]             - Show pending files to be uploaded with the next prompt"
        )
        self.console.print(
            "[bold blue]/clearfiles[/bold blue]         - Clear all pending files without sending"
        )
        self.console.print(
            "[bold blue]/help[/bold blue]               - Show this help message"
        )
        self.console.print(
            "[bold blue]/exit | /quit[/bold blue]       - End the chat session\n"
        )

    def load_or_create(self):
        """Loads messages if session exists (and displays them), otherwise creates it."""
        if self._needs_naming:
            self.console.print(
                "[bold green]✨ Starting new chat. Session will be named after your first message.[/bold green]"
            )
            self.messages = []
            return
        if not self.session_id:
            raise SessionError("Session ID is unexpectedly missing.")
        try:
            self.messages = self.session_manager.load_messages(self.session_id)
            self.console.print(
                f"[bold green]🔄 Resuming session: {self.display_name} (ID: {self.session_id})[/bold green]"
            )
            self._display_history()
        except FileNotFoundError:
            try:
                self.session_manager.create(self.session_id)
                self.messages = []
                self.console.print(
                    f"[bold green]✨ Started new session: {self.display_name} (ID: {self.session_id})[/bold green]"
                )
            except (SessionError, FileExistsError) as e:
                self.console.print(
                    f"[bold red]❌ Error creating session file '{self.session_id}': {escape(str(e))}[/bold red]"
                )
                raise
        except SessionError as e:
            self.console.print(
                f"[bold red]❌ Error loading session '{self.session_id}': {escape(str(e))}[/bold red]"
            )
            raise

    def _add_message(self, role: str, content: str):
        """Adds a message locally and persists it."""
        if not self.session_id:
            self.console.print(
                "[bold yellow]⚠️ Cannot save message: Session ID not yet determined.[/bold yellow]"
            )
            return
        self.messages.append({"role": role, "content": content})
        try:
            self.session_manager.append_message(self.session_id, role, content)
        except SessionError as e:
            self.console.print(
                f"[bold red]❌ Error saving message: {escape(str(e))}[/bold red]"
            )

    def _generate_and_set_session_name(self, first_user_message: str) -> bool:
        """Generates session name via AI, creates session file, sets self.session_id. Returns True on success."""
        ai_reply_name = None
        try:
            prompt_text = (
                "Based on the following user message, generate a concise, 2-4 word title "
                "suitable for a filename (use lowercase words, separated by hyphens). "
                "Example: 'analyze-stock-data'. Do not include any explanation, just the title.\n\n"
                f'User Message: "{first_user_message}"'
            )
            with self.console.status(
                "[yellow]💬 Generating session name...[/yellow]", spinner="dots"
            ):
                ai_reply_name = self.ai_client.get_completion(
                    messages=[{"role": "user", "content": prompt_text}], temperature=0.3
                )
            if ai_reply_name:
                ai_reply_name = ai_reply_name.strip().strip("'\"")
                sanitized_name = re.sub(r"\s+", "-", ai_reply_name.lower())
                sanitized_name = re.sub(r"[^\w\-]+", "", sanitized_name)
                sanitized_name = "-".join(sanitized_name.split("-")[:4])
            else:
                sanitized_name = ""
            if not sanitized_name:
                sanitized_name = "chat"
            temp_session_id = self.session_manager._generate_full_session_id(
                sanitized_name
            )
            self.session_manager.create(temp_session_id)
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
            traceback.print_exc()
        self.console.print(
            "[bold yellow]⚠️ Session naming failed. Please try starting your chat again.[/bold yellow]"
        )
        return False

    def _handle_rename(self, user_input: str):
        """Handles the /rename command."""
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
            new_full_id = self.session_manager.rename(old_full_id, new_display_name)
            if new_full_id and new_full_id != old_full_id:
                self.session_id = new_full_id
                self.console.print(
                    f"[bold green]✅ Session renamed from '{old_display_name}' to '{self.display_name}'[/bold green]"
                )
        except (FileNotFoundError, FileExistsError, SessionError, ValueError) as e:
            self.console.print(
                f"[bold red]❌ Rename failed: {escape(str(e))}[/bold red]"
            )

    def _handle_history(self):
        """Handles the /history command."""
        self._display_history()

    def _handle_clear(self):
        """Handles the /clear command."""
        if not self.session_id:
            self.console.print(
                "[bold red]❌ Cannot clear history: Session ID not yet determined.[/bold red]"
            )
            return
        confirm = (
            input(
                f"[bold yellow]❓ Are you sure you want to clear all history for session '{self.display_name}'? This cannot be undone. (y/N): [/bold yellow]"
            )
            .strip()
            .lower()
        )
        if confirm == "y":
            self.messages = []
            try:
                self.session_manager.save_messages(self.session_id, self.messages)
                self.console.print(
                    f"[bold green]✅ History for session '{self.display_name}' cleared.[/bold green]"
                )
            except SessionError as e:
                self.console.print(
                    f"[bold red]❌ Error clearing session history: {escape(str(e))}[/bold red]"
                )
        else:
            self.console.print("[italic]Clear operation cancelled.[/italic]")

    def _handle_upload(self, user_input: str):
        """Handles the /upload command: validates file, reads content, appends to pending list if not already added."""
        parts = user_input.split(maxsplit=1)
        file_path_str = None
        selected_path_obj = None

        if len(parts) > 1:
            file_path_str = parts[1].strip()
            selected_path_obj = Path(file_path_str).expanduser().resolve()
        else:
            fzf_path = shutil.which("fzf")
            if fzf_path:
                self.console.print("[cyan]Launching fzf file picker...[/cyan]")
                try:
                    result = subprocess.run(
                        [fzf_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    if result.returncode == 0 and result.stdout:
                        selected_path_str = result.stdout.strip()
                        selected_path_obj = Path(selected_path_str).resolve()
                        file_path_str = (
                            selected_path_str  # Keep original string for messages
                        )
                        self.console.print(
                            f"[cyan]Selected via fzf: {selected_path_str}[/cyan]"
                        )
                    elif result.returncode == 130:
                        self.console.print("[yellow]File selection cancelled.")
                        return
                    else:
                        error_msg = (
                            result.stderr.strip()
                            if result.stderr
                            else f"fzf exited with code {result.returncode}"
                        )
                        self.console.print(
                            f"[bold red]❌ fzf selection failed:[/bold red] {error_msg}"
                        )
                        return
                except Exception as e:
                    self.console.print(
                        f"[bold red]❌ Error running fzf: {escape(str(e))}[/bold red]"
                    )
                    traceback.print_exc()
                    return
            else:
                self.console.print("[bold red]❌ 'fzf' command not found.[/bold red]")
                self.console.print(
                    "[yellow]💡 Please install fzf (https://github.com/junegunn/fzf) for interactive selection,"
                )
                self.console.print(
                    "[yellow]   or provide the file path directly: /upload <file_path>[/yellow]"
                )
                return

        if selected_path_obj:
            try:
                # --- Check if path already added ---
                resolved_path_str = str(selected_path_obj)
                if resolved_path_str in self._pending_file_paths:
                    self.console.print(
                        f"[yellow]⚠️ File '{selected_path_obj.name}' is already staged for the next prompt.[/yellow]"
                    )
                    return  # Don't add again
                # --- End Check ---

                # Validation
                if not selected_path_obj.exists():
                    self.console.print(
                        f"[bold red]❌ File not found: {file_path_str}[/bold red]"
                    )
                    return
                if not selected_path_obj.is_file():
                    self.console.print(
                        f"[bold red]❌ Path is not a file: {file_path_str}[/bold red]"
                    )
                    return
                if self.ALLOWED_EXTENSIONS:
                    file_ext = selected_path_obj.suffix.lower()
                    if file_ext not in self.ALLOWED_EXTENSIONS:
                        allowed_str = ", ".join(self.ALLOWED_EXTENSIONS)
                        self.console.print(
                            f"[bold red]❌ Invalid file type '{file_ext}'. Allowed: {allowed_str}[/bold red]"
                        )
                        return
                file_size = selected_path_obj.stat().st_size
                max_size_bytes = self.MAX_UPLOAD_SIZE_KB * 1024
                if file_size > max_size_bytes:
                    self.console.print(
                        f"[bold red]❌ File is too large ({file_size / 1024:.1f} KB). Max: {self.MAX_UPLOAD_SIZE_KB} KB.[/bold red]"
                    )
                    return
                if file_size == 0:
                    self.console.print(
                        f"[bold yellow]⚠️ File is empty: {file_path_str}[/bold yellow]"
                    )

                # Read and Append
                try:
                    content = selected_path_obj.read_text(encoding="utf-8")
                    # Add to list AND set
                    self._pending_files.append((selected_path_obj.name, content))
                    self._pending_file_paths.add(resolved_path_str)  # Add path to set
                    # ---
                    file_size_kb = file_size / 1024
                    self.console.print(
                        f"[bold green]✅ File '{selected_path_obj.name}' staged ({file_size_kb:.1f} KB).[/bold green]"
                    )
                    self.console.print(
                        "[cyan]   Use /status to view pending files, /clearfiles to remove.[/cyan]"
                    )
                except UnicodeDecodeError:
                    self.console.print(
                        f"[bold red]❌ Could not read file as UTF-8 text: {file_path_str}. Might be binary?[/bold red]"
                    )
                except IOError as e:
                    self.console.print(
                        f"[bold red]❌ Error reading file: {e}[/bold red]"
                    )
            except OSError as e:
                self.console.print(
                    f"[bold red]❌ Error accessing file path: {e}[/bold red]"
                )
            except Exception as e:
                self.console.print(
                    f"[bold red]❌ Unexpected error processing file: {escape(str(e))}[/bold red]"
                )
                traceback.print_exc()

    def _handle_edit(self) -> Optional[str]:
        """Opens $EDITOR for multi-line input, returns content or None."""
        editor = os.getenv("EDITOR")
        if not editor:
            self.console.print(
                "[bold red]❌ $EDITOR environment variable not set.[/bold red]"
            )
            self.console.print(
                "[yellow]   Please set $EDITOR to your preferred text editor (e.g., vim, nano, code).[/yellow]"
            )
            return None

        temp_file_path_str = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+t", suffix=".md", delete=False, encoding="utf-8"
            ) as tf:
                temp_file_path_str = tf.name
                tf.write(
                    "# Enter your prompt below. Save and exit the editor when done.\n"
                )
                tf.flush()

            self.console.print(
                f"[cyan]Opening editor ('{editor}') for input. Save and exit when done.[/cyan]"
            )
            editor_cmd = [editor, temp_file_path_str]
            process = subprocess.run(editor_cmd)

            if process.returncode != 0:
                self.console.print(
                    f"[bold yellow]⚠️ Editor exited with status {process.returncode}. Input might not be saved correctly.[/bold yellow]"
                )

            if temp_file_path_str and Path(temp_file_path_str).exists():
                content = Path(temp_file_path_str).read_text(encoding="utf-8").strip()
                if content.startswith("# Enter your prompt below."):
                    lines = content.split("\n", 1)
                    content = lines[1].strip() if len(lines) > 1 else ""
                return content
            else:
                self.console.print(
                    "[bold red]❌ Temporary file not found after editing.[/bold red]"
                )
                return None
        except FileNotFoundError:
            self.console.print(
                f"[bold red]❌ Editor command not found: '{editor}'[/bold red]"
            )
            self.console.print(
                "[yellow]   Ensure $EDITOR is set correctly and the editor is in your PATH.[/yellow]"
            )
            return None
        except Exception as e:
            self.console.print(
                f"[bold red]❌ Error during editor process: {escape(str(e))}[/bold red]"
            )
            traceback.print_exc()
            return None
        finally:
            if temp_file_path_str and Path(temp_file_path_str).exists():
                try:
                    Path(temp_file_path_str).unlink()
                except OSError as e:
                    self.console.print(
                        f"[bold yellow]⚠️ Could not delete temporary file {temp_file_path_str}: {e}[/bold yellow]"
                    )

    def _handle_status(self):
        """Displays the list of currently pending files."""
        if not self._pending_files:
            self.console.print("[yellow]No files pending for the next prompt.[/yellow]")
        else:
            self.console.print(
                f"[bold cyan]Pending files ({len(self._pending_files)}):[/bold cyan]"
            )
            total_kb = 0
            for i, (fname, content) in enumerate(self._pending_files):
                content_kb = len(content.encode("utf-8")) / 1024
                total_kb += content_kb
                self.console.print(f"  {i+1}. {escape(fname)} ({content_kb:.1f} KB)")
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
            self._pending_file_paths.clear()  # Clear the set as well
            self.console.print(
                f"[bold green]✅ Cleared {num_cleared} pending file(s).[/bold green]"
            )

    def run_interaction_loop(self):
        """Runs the main interactive input loop."""
        if not self._needs_naming:
            self.console.print(
                "[bold blue]Type '/help' for commands, '/exit' or '/quit' to end.[/bold blue]"
            )
        while True:
            try:
                # Print Prompt (Shows Filenames)
                self.console.print(
                    f"\n[bold cyan]{self.display_name}[/bold cyan]", end=""
                )
                if self._pending_files:
                    filenames = [escape(fname) for fname, _ in self._pending_files]
                    display_filenames = filenames[: self.MAX_FILENAMES_IN_PROMPT]
                    files_text_str = ", ".join(display_filenames)
                    if len(filenames) > self.MAX_FILENAMES_IN_PROMPT:
                        files_text_str += f", ... ({len(filenames)} total)"
                    file_info_text = Text(
                        f" (Files: {files_text_str})", style="italic yellow"
                    )
                    self.console.print(" ", file_info_text, end="")
                self.console.print(" [bold cyan]> You[/bold cyan]: ", end="")

                user_input = input().strip()  # Use standard input

                if user_input.lower() in ["/exit", "/quit"]:
                    self.console.print(
                        "[bold magenta]👋 Exiting session.[/bold magenta]"
                    )
                    break

                # Process Commands
                is_command = user_input.startswith("/")
                edited_content = None
                if is_command:
                    if user_input.lower() == "/help":
                        self._show_help()
                        continue
                    elif user_input.lower() == "/edit":
                        edited_content = self._handle_edit()
                        if edited_content is None:
                            continue
                        else:
                            user_input = edited_content
                            is_command = False
                    elif user_input.lower().startswith("/upload"):
                        self._handle_upload(user_input)
                        continue
                    elif user_input.lower() == "/status":
                        self._handle_status()
                        continue
                    elif user_input.lower() == "/clearfiles":
                        self._handle_clear_files()
                        continue
                    elif self.session_id:  # Other commands requiring ID
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
                                f"[yellow]⚠️ Unknown command: {user_input}[/yellow]"
                            )
                            continue
                    else:
                        self.console.print(
                            "[yellow]⚠️ Cannot run this command until the session is named...[/yellow]"
                        )
                        continue

                # Process Regular Message (or content from /edit)
                if user_input and not is_command:
                    if self._needs_naming:
                        naming_success = self._generate_and_set_session_name(user_input)
                        if not naming_success:
                            continue

                    if self.session_id:
                        # Build context, clear list AND set after use
                        final_user_content = user_input
                        if self._pending_files:
                            context_prefix = ""
                            for i, (fname, fcontent) in enumerate(self._pending_files):
                                escaped_fname_for_ai = escape(fname)
                                context_prefix += (
                                    f"[User uploaded file {i+1}: '{escaped_fname_for_ai}']\n"
                                    f"--- File Content Start ({escaped_fname_for_ai}) ---\n"
                                    f"{fcontent}\n"
                                    f"--- File Content End ({escaped_fname_for_ai}) ---\n\n"
                                )
                            final_user_content = context_prefix + user_input
                            # Clear both list and set after use
                            self._pending_files = []
                            self._pending_file_paths.clear()

                        self._add_message("user", final_user_content)
                        try:
                            self.console.print(
                                f"\n[bold green]{self.display_name} > AI[/bold green]: ",
                                end="",
                            )
                            ai_reply = ""
                            with self.console.status(
                                "[yellow]🧠 Thinking...[/yellow]", spinner="dots"
                            ):
                                ai_reply = self.ai_client.get_completion(self.messages)

                            if ai_reply:
                                md = Markdown(
                                    ai_reply,
                                    code_theme=self.CODE_THEME,
                                    inline_code_theme=self.CODE_THEME,
                                )
                                self.console.print(md)
                                self._add_message("assistant", ai_reply)
                            else:
                                self.console.print(
                                    "[italic yellow](Empty response received)[/italic]"
                                )
                        except AIClientError as e:
                            self.console.print(
                                f"[bold red]\n❌ AI Error: {escape(str(e))}[/bold red]"
                            )
                            continue
                        except Exception as e:
                            self.console.print(
                                f"[bold red]\n❌ Unexpected Error during AI call: {escape(str(e))}[/bold red]"
                            )
                            traceback.print_exc()
                            continue

            # Exception Handling
            except EOFError:
                self.console.print(
                    "\n[bold magenta]👋 Exiting session (EOF detected).[/bold magenta]"
                )
                break
            except KeyboardInterrupt:
                # Clear pending files list AND set on interrupt
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
            except Exception as e:
                self.console.print(
                    f"[bold red]\n❌ Unexpected Error in interaction loop: {escape(str(e))}[/bold red]"
                )
                traceback.print_exc()
                break
