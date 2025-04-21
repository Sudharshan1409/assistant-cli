# utils/session_manager.py
"""
Manages the persistence of chat session history files.

Handles creating, loading, saving, listing, renaming, and deleting
session files stored as JSON in the designated session directory.
"""

import json
import re
import sys  # Import sys for traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import constants
from constants import MAX_SESSION_NAME_LEN, SESSION_DIR, SESSION_ID_SUFFIX_RE


class SessionError(Exception):
    """Custom exception for session management errors."""

    pass


class SessionManager:
    """Handles CRUD operations and listing for chat session files."""

    def __init__(self, session_dir: Optional[Path] = None):
        """
        Initializes the SessionManager.

        Args:
            session_dir: Optional path to the session directory.
                         Defaults to SESSION_DIR from constants.
        """
        # Use session directory from constants if not provided
        self.session_dir = session_dir or SESSION_DIR
        self._ensure_session_dir_exists()

    def _ensure_session_dir_exists(self):
        """Ensures the session directory exists, creating it if necessary."""
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise SessionError(
                f"Could not create session directory {self.session_dir}: {e}"
            )

    def _sanitize_filename(self, name: str) -> str:
        """Removes or replaces characters problematic for filenames."""
        # Remove leading/trailing whitespace/dots/underscores/hyphens
        name = name.strip(". _-")
        # Replace whitespace sequences with a single hyphen
        name = re.sub(r"\s+", "-", name)
        # Remove characters not allowed (allow letters, numbers, underscore, hyphen)
        name = re.sub(r"[^\w\-]+", "", name)
        # Limit length (using constant)
        name = name[:MAX_SESSION_NAME_LEN]
        # Fallback if empty after sanitization
        return name or "unnamed-session"

    def _get_session_path(self, full_session_id: str) -> Path:
        """
        Constructs the absolute path to a session file.

        Important: This assumes full_session_id is already generated and valid.
        It performs minimal safety checks for path construction.

        Args:
            full_session_id: The complete session ID (e.g., 'my-chat_a1b2c3d4').

        Returns:
            The Path object for the session's JSON file.

        Raises:
            ValueError: If the session ID is invalid or empty.
        """
        if not full_session_id or not isinstance(full_session_id, str):
            raise ValueError("Invalid or empty session_id provided.")
        # Basic check for path traversal characters (though sanitization should prevent)
        if "/" in full_session_id or "\\" in full_session_id or ".." in full_session_id:
            raise ValueError(
                f"Invalid characters found in session ID: {full_session_id}"
            )
        return self.session_dir / f"{full_session_id}.json"

    def _split_session_id(self, full_session_id: str) -> Tuple[str, Optional[str]]:
        """
        Splits a full session ID (e.g., 'my-chat_a1b2c3d4') into its name
        and UUID suffix parts.

        Args:
            full_session_id: The complete session ID string.

        Returns:
            A tuple containing (display_name, uuid_suffix) or (display_name, None)
            if the standard suffix pattern isn't found.
        """
        match = SESSION_ID_SUFFIX_RE.search(full_session_id)  # Use regex from constants
        if match:
            name_part = full_session_id[: match.start()]
            uuid_part = full_session_id[match.start() + 1 :]  # Skip the underscore
            return name_part, uuid_part
        else:
            # Treat the whole ID as the name part if no suffix matches
            return full_session_id, None

    def _generate_full_session_id(self, display_name: str) -> str:
        """
        Generates a unique full session ID (name_uuid) for a given display name.

        Sanitizes the name, appends a unique suffix, and ensures the resulting
        ID does not correspond to an existing session file.

        Args:
            display_name: The desired user-facing name for the session.

        Returns:
            A unique session ID string (e.g., 'sanitized-name_uuidpart').
        """
        sanitized_name = self._sanitize_filename(display_name)
        while True:
            # Generate short unique suffix
            unique_suffix = str(uuid.uuid4())[:8]
            full_id = f"{sanitized_name}_{unique_suffix}"
            # Check for file existence using the path generation method
            if not self._get_session_path(full_id).exists():
                return full_id

    def rename(self, old_full_session_id: str, new_display_name: str) -> Optional[str]:
        """
        Renames a session file while preserving its unique suffix.

        Args:
            old_full_session_id: The current full ID of the session to rename.
            new_display_name: The desired new display name.

        Returns:
            The new full session ID if successful, None if the name didn't change
            or resulted in the same final ID.

        Raises:
            ValueError: If the new display name is empty.
            FileNotFoundError: If the old session file doesn't exist.
            FileExistsError: If a different session file already exists at the target path.
            SessionError: For other OS-level errors during renaming.
        """
        if not new_display_name:
            raise ValueError("New session name cannot be empty.")

        old_path = self._get_session_path(old_full_session_id)
        if not old_path.is_file():  # More specific check than exists()
            raise FileNotFoundError(f"Session file not found: {old_path}")

        _, uuid_suffix = self._split_session_id(old_full_session_id)
        # Sanitize the new desired name
        sanitized_new_name = self._sanitize_filename(new_display_name)

        if uuid_suffix is None:
            # If old ID had no suffix, generate a completely new unique ID
            # This preserves the *content* but gives it a standard ID format
            new_full_id = self._generate_full_session_id(sanitized_new_name)
            print(
                f"[yellow]Warning: Old session ID '{old_full_session_id}' lacked standard suffix. Generating new ID: '{new_full_id}'[/]",
                file=sys.stderr,
            )
        else:
            # Construct new ID using sanitized name and existing suffix
            new_full_id = f"{sanitized_new_name}_{uuid_suffix}"

        # Check if renaming is actually necessary
        if old_full_session_id == new_full_id:
            return None  # No change needed

        new_path = self._get_session_path(new_full_id)

        # Check if the target path *already exists* and is *not the same file*
        if new_path.exists():
            if new_path.samefile(
                old_path
            ):  # Check if they point to the same file inode
                return None  # Effectively no change needed (e.g., case change on case-insensitive FS)
            else:
                raise FileExistsError(
                    f"Another session file already exists at target path: {new_path}"
                )

        # Perform the rename operation
        try:
            old_path.rename(new_path)
            return new_full_id  # Return the new ID on success
        except OSError as e:
            raise SessionError(
                f"Failed to rename session from '{old_path.name}' to '{new_path.name}': {e}"
            )
        except Exception as e:
            raise SessionError(f"Unexpected error during rename: {e}")

    def create(self, full_session_id: str):
        """Creates an empty session file containing an empty JSON list `[]`."""
        path = self._get_session_path(full_session_id)
        if path.exists():
            raise FileExistsError(f"Session file already exists: {path}")
        try:
            # Write an empty list as the initial content
            path.write_text("[]", encoding="utf-8")
        except IOError as e:
            raise SessionError(f"Failed to create session file '{path.name}': {e}")
        except Exception as e:
            raise SessionError(
                f"Unexpected error creating session file '{path.name}': {e}"
            )

    def save_messages(self, full_session_id: str, messages: List[Dict[str, str]]):
        """Saves the provided message list to the session file (overwrites)."""
        path = self._get_session_path(full_session_id)
        try:
            # Write the message list, pretty-printed
            path.write_text(json.dumps(messages, indent=2), encoding="utf-8")
        except IOError as e:
            raise SessionError(
                f"Failed to save messages for session '{path.name}': {e}"
            )
        except TypeError as e:  # Handle non-serializable data in messages
            raise SessionError(
                f"Invalid message data format for session '{path.name}': {e}"
            )
        except Exception as e:
            raise SessionError(
                f"Unexpected error saving messages for session '{path.name}': {e}"
            )

    def load_messages(self, full_session_id: str) -> List[Dict[str, str]]:
        """Loads the message list from a session file."""
        path = self._get_session_path(full_session_id)
        if not path.is_file():
            raise FileNotFoundError(f"Session file not found: {path}")
        try:
            content = path.read_text(encoding="utf-8")
            if not content.strip():
                return []  # Return empty list if file is empty

            data = json.loads(content)
            # Basic validation: ensure it's a list
            if not isinstance(data, list):
                raise SessionError(
                    f"Invalid format in session file '{path.name}'. Expected a JSON list."
                )
            # Further validation could check if list items are dictionaries with 'role' and 'content'

            return data
        except json.JSONDecodeError as e:
            raise SessionError(
                f"Error decoding JSON from session file '{path.name}': {e}"
            )
        except IOError as e:
            raise SessionError(f"Error reading session file '{path.name}': {e}")
        except Exception as e:
            raise SessionError(
                f"Unexpected error loading messages from session '{path.name}': {e}"
            )

    def append_message(self, full_session_id: str, role: str, content: str):
        """
        Appends a single message to the session file.

        This is less efficient than loading all, modifying, and saving all,
        but ensures persistence after each message.
        """
        if not full_session_id:
            raise ValueError("Cannot append message: session ID is missing.")
        try:
            # Load existing messages
            messages = self.load_messages(full_session_id)
            # Append the new message
            messages.append({"role": role, "content": content})
            # Save the updated list back
            self.save_messages(full_session_id, messages)
        # Propagate errors from load/save
        except (SessionError, FileNotFoundError, ValueError) as e:
            raise SessionError(
                f"Failed to append message to session '{full_session_id}': {e}"
            )
        except Exception as e:
            raise SessionError(
                f"Unexpected error appending message to session '{full_session_id}': {e}"
            )

    def list_sessions(self) -> List[Tuple[str, str]]:
        """
        Lists available sessions, sorted by modification time (latest first).

        Returns:
            A list of tuples: (display_name, full_session_id)
        """
        sessions_with_time = []
        try:
            # Ensure directory exists before globbing
            self._ensure_session_dir_exists()
            for session_file_path in self.session_dir.glob("*.json"):
                if session_file_path.is_file():
                    try:
                        mtime = session_file_path.stat().st_mtime
                        full_id = session_file_path.stem  # Filename without .json
                        # Extract display name using the helper
                        display_name, _ = self._split_session_id(full_id)
                        sessions_with_time.append((display_name, full_id, mtime))
                    except OSError:
                        # Skip files that cannot be stat'ed (e.g., permissions)
                        print(
                            f"[yellow]Warning: Could not access session file info: {session_file_path.name}[/]",
                            file=sys.stderr,
                        )
                        continue
                    except ValueError:
                        # Skip files whose names don't parse correctly
                        print(
                            f"[yellow]Warning: Skipping session file with unexpected name format: {session_file_path.name}[/]",
                            file=sys.stderr,
                        )
                        continue

            # Sort by modification time (descending)
            sessions_with_time.sort(key=lambda item: item[2], reverse=True)

            # Return only the display name and full ID
            return [(disp_name, f_id) for disp_name, f_id, mtime in sessions_with_time]

        except OSError as e:
            # Handle error during initial directory listing
            raise SessionError(
                f"Error listing sessions directory {self.session_dir}: {e}"
            )
        except Exception as e:
            raise SessionError(f"Unexpected error listing sessions: {e}")

    def session_exists(self, full_session_id: str) -> bool:
        """Checks if a session file exists for the given full ID."""
        try:
            path = self._get_session_path(full_session_id)
            return path.is_file()
        except ValueError:
            return False  # Invalid ID format cannot exist
        except OSError:
            return False  # Cannot access path

    def delete_session(self, full_session_id: str):
        """Deletes the session file corresponding to the full ID."""
        try:
            path = self._get_session_path(full_session_id)
            if not path.is_file():
                raise FileNotFoundError(f"Session file not found for deletion: {path}")
            # Attempt to delete the file
            path.unlink()
        except (ValueError, FileNotFoundError) as e:
            # Re-raise specific errors for clarity
            raise e
        except OSError as e:
            # Handle OS errors during deletion (e.g., permissions)
            raise SessionError(f"Failed to delete session file '{path.name}': {e}")
        except Exception as e:
            raise SessionError(
                f"Unexpected error deleting session '{full_session_id}': {e}"
            )
