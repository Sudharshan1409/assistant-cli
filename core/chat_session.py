# core/chat_session.py
import re
import traceback
from typing import Dict, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape

from utils.ai_client import AIClient, AIClientError

# Import the manager/client classes
from utils.session_manager import SessionError, SessionManager


class ChatSession:
    """Represents and manages an active chat session interaction."""

    CODE_THEME = "native"

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
        if self.session_id:
            name, _ = self.session_manager._split_session_id(self.session_id)
            return name
        elif self._needs_naming:
            return "[Pending Name]"
        else:
            return "[Unnamed Session]"

    def _display_history(self, limit: Optional[int] = None):
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
            md = Markdown(
                content, code_theme=self.CODE_THEME, inline_code_theme=self.CODE_THEME
            )
            self.console.print(md)
        self.console.print("-" * 20)

    def _show_help(self):
        self.console.print("\n[bold green]Available Commands:[/bold green]")
        self.console.print(
            f"[bold blue]/rename [new_name][/bold blue] - Rename the current session '{self.display_name}'"
        )
        self.console.print(
            "[bold blue]/history[/bold blue] - Show current session message history"
        )
        self.console.print(
            "[bold blue]/clear[/bold blue] - Clear current session message history (cannot be undone)"
        )
        self.console.print("[bold blue]/help[/bold blue] - Show this help message")
        self.console.print(
            "[bold blue]/exit | /quit[/bold blue] - End the chat session\n"
        )

    def load_or_create(self):
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

    def _generate_and_set_session_name(self, first_user_message: str):
        ai_reply_name = None
        try:
            prompt = (
                "Based on the following user message, generate a concise, 2-4 word title "
                "suitable for a filename (use lowercase words, separated by hyphens). "
                "Example: 'analyze-stock-data'. Do not include any explanation, just the title.\n\n"
                f'User Message: "{first_user_message}"'
            )
            with self.console.status(
                "[yellow]💬 Generating session name...[/yellow]", spinner="dots"
            ):
                ai_reply_name = self.ai_client.get_completion(
                    messages=[{"role": "user", "content": prompt}], temperature=0.3
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
        self._display_history()

    def _handle_clear(self):
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

    def run_interaction_loop(self):
        if not self._needs_naming:
            self.console.print(
                "[bold blue]Type '/help' for commands, '/exit' or '/quit' to end.[/bold blue]"
            )
        while True:
            try:
                self.console.print(
                    f"\n[bold cyan]{self.display_name} > You[/bold cyan]: ", end=""
                )
                user_input = input().strip()
                if user_input.lower() in ["/exit", "/quit"]:
                    self.console.print(
                        "[bold magenta]👋 Exiting session.[/bold magenta]"
                    )
                    break
                is_command = user_input.startswith("/")
                if is_command:
                    if user_input.lower() == "/help":
                        self._show_help()
                        continue
                    if self.session_id:
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
                            "[yellow]⚠️ Cannot run this command until the session is named (after your first message).[/yellow]"
                        )
                        continue
                if user_input:
                    if self._needs_naming:
                        naming_success = self._generate_and_set_session_name(user_input)
                        if not naming_success:
                            continue
                    if self.session_id:
                        self._add_message("user", user_input)
                        try:
                            # --- CORRECTED LINE (no flush) ---
                            self.console.print(
                                f"\n[bold green]{self.display_name} > AI[/bold green]: ",
                                end="",
                            )
                            # --- END CORRECTED LINE ---
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
            except EOFError:
                self.console.print(
                    "\n[bold magenta]👋 Exiting session (EOF detected).[/bold magenta]"
                )
                break
            except KeyboardInterrupt:
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
