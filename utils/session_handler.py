import json
import os
from pathlib import Path

SESSION_DIR = Path.home() / ".ai-cli" / "chat_sessions"

# Ensure the session directory exists
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def session_path(session_id):
    return SESSION_DIR / f"{session_id}.json"


def rename_session(old_name: str, new_name: str) -> bool:
    old_path = os.path.join(SESSION_DIR, f"{old_name}.json")
    new_path = os.path.join(SESSION_DIR, f"{new_name}.json")

    if not os.path.exists(old_path):
        return False

    if os.path.exists(new_path):
        raise FileExistsError(f"Session '{new_name}' already exists!")

    os.rename(old_path, new_path)
    return True


def create_session(session_id):
    path = session_path(session_id)
    with open(path, "w") as f:
        json.dump([], f)


def save_message(session_id, role, content):
    path = session_path(session_id)
    messages = load_session_messages(session_id)
    messages.append({"role": role, "content": content})
    with open(path, "w") as f:
        json.dump(messages, f, indent=2)


def load_session_messages(session_id):
    path = session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"Session {session_id} not found")
    with open(path, "r") as f:
        return json.load(f)


def list_sessions():
    return [f.stem for f in SESSION_DIR.glob("*.json")]
