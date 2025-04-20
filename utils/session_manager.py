# utils/session_manager.py
import json
import re  # Import regex
import uuid  # Import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class SessionError(Exception):
    """Custom exception for session errors."""

    pass


class SessionManager:
    """Manages chat session persistence (CRUD, list, rename)."""

    DEFAULT_SESSION_DIR = Path.home() / ".ai-cli" / "chat_sessions"
    # Regex to match the _{uuid} suffix (e.g., _a1b2c3d4)
    SESSION_ID_SUFFIX_RE = re.compile(
        r"_(?:[a-f0-9]{8})$"
    )  # Non-capturing group for UUID

    def __init__(self, session_dir: Optional[Path] = None):
        self.session_dir = session_dir or self.DEFAULT_SESSION_DIR
        self._ensure_session_dir_exists()

    def _ensure_session_dir_exists(self):
        """Ensures the session directory exists."""
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, full_session_id: str) -> Path:
        """Constructs the path to a session file using the full ID (name_uuid)."""
        if not full_session_id or not isinstance(full_session_id, str):
            raise ValueError("Invalid session_id provided.")
        # Basic sanitization - replace potentially problematic chars if needed
        # Ensure we don't sanitize the separator '_' if it's part of the name
        safe_session_id = full_session_id  # Assume IDs are already safe
        return self.session_dir / f"{safe_session_id}.json"

    def _split_session_id(self, full_session_id: str) -> Tuple[str, Optional[str]]:
        """Splits 'name_uuid' into ('name', 'uuid') or ('name', None)."""
        match = self.SESSION_ID_SUFFIX_RE.search(full_session_id)
        if match:
            # Found the suffix, split it
            name_part = full_session_id[: match.start()]
            uuid_part = full_session_id[match.start() + 1 :]  # +1 to exclude underscore
            return name_part, uuid_part
        else:
            # No matching suffix, return the whole ID as name part
            return full_session_id, None

    def _generate_full_session_id(self, display_name: str) -> str:
        """Generates a unique full ID (name_uuid) for a given display name."""
        # Sanitize display name for filesystem use (lowercase, replace space with hyphen)
        sanitized_name = re.sub(r"\s+", "-", display_name.lower())
        sanitized_name = re.sub(
            r"[^\w\-]+", "", sanitized_name
        )  # Keep word chars, hyphens
        sanitized_name = (
            sanitized_name or "session"
        )  # Fallback if name is empty after sanitization

        while True:
            unique_suffix = str(uuid.uuid4())[:8]
            full_id = f"{sanitized_name}_{unique_suffix}"
            if not self.session_exists(full_id):
                return full_id

    def rename(self, old_full_session_id: str, new_display_name: str):
        """Renames a session file, preserving the UUID suffix."""
        if not new_display_name:
            raise ValueError("New session name cannot be empty.")

        old_path = self._get_session_path(old_full_session_id)
        if not old_path.exists():
            raise FileNotFoundError(
                f"Session with ID '{old_full_session_id}' not found."
            )

        _, uuid_suffix = self._split_session_id(old_full_session_id)
        if uuid_suffix is None:
            # Handle renaming sessions that don't follow the new pattern?
            # For now, let's assume we only rename sessions with UUIDs this way.
            # Or generate a new UUID if one wasn't present?
            # Let's just generate a new full ID based on the new name
            new_full_id = self._generate_full_session_id(new_display_name)
            print(
                f"[yellow]Warning: Old session ID '{old_full_session_id}' did not have standard suffix. Generating new ID.[/yellow]"
            )
        else:
            # Sanitize new display name
            sanitized_new_name = re.sub(r"\s+", "-", new_display_name.lower())
            sanitized_new_name = re.sub(r"[^\w\-]+", "", sanitized_new_name)
            sanitized_new_name = sanitized_new_name or "session"
            new_full_id = f"{sanitized_new_name}_{uuid_suffix}"

        if old_full_session_id == new_full_id:
            print(
                "[yellow]New name is the same as the old name. No changes made.[/yellow]"
            )
            return  # Or raise ValueError("New name is the same as the old name.")

        new_path = self._get_session_path(new_full_id)

        if new_path.exists():
            # This check is important if UUIDs are reused (they shouldn't be, but safety first)
            raise FileExistsError(
                f"A session interfering with '{new_display_name}' (target: {new_full_id}) already exists."
            )

        try:
            old_path.rename(new_path)
            return new_full_id  # Return the new full ID
        except OSError as e:
            raise SessionError(
                f"Failed to rename session from '{old_full_session_id}' to '{new_full_id}': {e}"
            )

    def create(self, full_session_id: str):
        """Creates an empty session file using the full ID."""
        path = self._get_session_path(full_session_id)
        if path.exists():
            raise FileExistsError(
                f"Session file '{full_session_id}.json' already exists."
            )
        try:
            with path.open("w") as f:
                json.dump([], f)
        except IOError as e:
            raise SessionError(
                f"Failed to create session file '{full_session_id}': {e}"
            )

    def save_messages(self, full_session_id: str, messages: List[Dict[str, str]]):
        """Saves messages using the full session ID."""
        path = self._get_session_path(full_session_id)
        # ... (rest of the save logic remains the same)
        try:
            with path.open("w") as f:
                json.dump(messages, f, indent=2)
        except IOError as e:
            raise SessionError(
                f"Failed to save messages for session '{full_session_id}': {e}"
            )
        except TypeError as e:
            raise SessionError(
                f"Invalid message format for session '{full_session_id}': {e}"
            )

    def load_messages(self, full_session_id: str) -> List[Dict[str, str]]:
        """Loads messages using the full session ID."""
        path = self._get_session_path(full_session_id)
        # ... (rest of the load logic remains the same)
        if not path.exists():
            raise FileNotFoundError(f"Session file '{full_session_id}.json' not found.")
        try:
            with path.open("r") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    raise SessionError(
                        f"Invalid format in session file '{full_session_id}'. Expected a list."
                    )
                return data
        except (json.JSONDecodeError, IOError) as e:
            raise SessionError(f"Error loading session file '{full_session_id}': {e}")

    def append_message(self, full_session_id: str, role: str, content: str):
        """Appends a single message using the full session ID."""
        # Ensure ID is valid before proceeding
        if not full_session_id:
            raise ValueError("Cannot append message with empty session ID.")
        messages = self.load_messages(full_session_id)
        messages.append({"role": role, "content": content})
        self.save_messages(full_session_id, messages)

    def list_sessions(self) -> List[Tuple[str, str]]:
        """
        Lists sessions as (display_name, full_id) tuples.
        Filters out the _{uuid} suffix for the display name.
        """
        sessions = []
        try:
            for f in self.session_dir.glob("*.json"):
                if f.is_file():
                    full_id = f.stem
                    display_name, _ = self._split_session_id(full_id)
                    sessions.append((display_name, full_id))
            # Sort by display name
            return sorted(sessions, key=lambda x: x[0])
        except OSError as e:
            raise SessionError(f"Error listing sessions in {self.session_dir}: {e}")

    def session_exists(self, full_session_id: str) -> bool:
        """Checks if a session file exists using the full ID."""
        return self._get_session_path(full_session_id).exists()

    def delete_session(self, full_session_id: str):
        """Deletes a session file using the full ID."""
        path = self._get_session_path(full_session_id)
        if not path.exists():
            raise FileNotFoundError(
                f"Session file '{full_session_id}.json' not found for deletion."
            )
        try:
            path.unlink()
        except OSError as e:
            raise SessionError(f"Failed to delete session '{full_session_id}': {e}")
