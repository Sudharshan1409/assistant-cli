# AI Assistant CLI

A powerful and user-friendly command-line interface (CLI) to interact with OpenAI's chat models (like GPT-3.5, GPT-4, GPT-4o). Built with Python using Typer, Rich, Questionary, and the OpenAI library.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Choose your license -->

## Overview

This CLI provides a seamless way to chat with AI models directly from your terminal. It supports both interactive chat sessions and direct non-interactive prompting.

**Interactive Sessions:** Start, resume, list, and delete persistent chat sessions with automatic session naming, rich Markdown rendering, loading indicators, file uploads, and in-chat commands (including editing multi-line input via `$EDITOR`).

**Direct Prompting:** Get quick answers from the AI without entering an interactive session. Supports piping data via `stdin`, providing file context, choosing output formats (Markdown, raw text, JSON), and saving results directly to files.

## Features

- **Interactive Chat Sessions (`session` command):**
  - Start new sessions (`session new`), optionally named (`--name`) or automatically named based on the first prompt.
  - Resume previous sessions via an interactive list (`session resume`).
  - List all saved sessions (`session list`), sorted by modification time (latest first).
  - Delete one or more sessions via an interactive checklist (`session delete`).
  - Persistent history saved for each session.
- **Direct Prompting (`prompt` command):**
  - Send a single prompt directly: `prompt "Your question"`
  - **Pipe `stdin`:** Process piped data: `cat file.txt | prompt "Summarize:"`
  - **File Context:** Provide a file as context: `prompt "Explain code" -f script.py` (Note: `stdin` takes precedence over `-f`).
  - **Output Formats:** Choose output: `markdown` (default), `raw`, `json` using `--output-format` (`-of`).
  - **Save to File:** Save the response directly: `prompt "Generate code" -o code.py`
- **Rich Output:** AI responses rendered using Markdown (default) for better readability:
  - Headings, lists, bold, italics, etc.
  - Syntax highlighting for code blocks (`python ... `).
- **Loading Indicator:** Shows a spinner animation while waiting for the AI response (both interactive and direct prompt).
- **File Handling (Interactive Session):**
  - Stage one or more files using `/upload [path]` or `/upload` (with `fzf` installed) to include their content in the _next_ prompt.
  - Check pending files with `/status`.
  - Clear pending files with `/clearfiles`.
  - Prevents adding the same file multiple times.
  - Configurable max file size and allowed extensions.
- **External Editor Support (Interactive Session):**
  - Use `/edit` command to open your default `$EDITOR` for composing multi-line input easily.
- **In-Chat Commands (Interactive Session):**
  - `/help`: Show available commands.
  - `/rename <new-name>`: Rename the current session.
  - `/history`: Display the conversation history so far.
  - `/clear`: Clear the history for the current session (irreversible!).
  - `/upload [path]`: Stage a file.
  - `/edit`: Open `$EDITOR` for input.
  - `/status`: View staged files.
  - `/clearfiles`: Remove staged files.
  - `/exit` or `/quit`: End the current chat session.
- **Secure Configuration:** Interactively set up your OpenAI API key and preferred model via `setup configure`. Reads `OPENAI_API_KEY` env var. Configuration stored locally.

## Installation

**Prerequisites:**

- Python 3.8 or higher.
- `pip` (Python package installer).
- An OpenAI account and API key. ([Get one here](https://platform.openai.com/signup))
- **(Optional but Recommended for `/upload`):** `fzf` ([Install Instructions](https://github.com/junegunn/fzf#installation)) for interactive file selection.

**Steps:**

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/Sudharshan1409/ai-cli.git # Replace with your repo URL
    cd ai-cli
    ```

2.  **Create and activate a virtual environment (Recommended):**

    - **macOS/Linux:**
      ```bash
      python3 -m venv venv
      source venv/bin/activate
      ```
    - **Windows:**
      ```bash
      python -m venv venv
      .\venv\Scripts\activate
      ```

3.  **Install dependencies:**
    ```bash
    pip install "typer[all]" rich openai questionary
    ```
    _(Or create `requirements.txt` and run `pip install -r requirements.txt`)_

## Configuration

Set up your OpenAI API key and choose a default model before use.

1.  **Run the setup command:**

    ```bash
    python main.py setup configure
    ```

2.  **Follow the prompts:**

    - It checks for the `OPENAI_API_KEY` environment variable or the `--openai-api-key` / `-k` option first.
    - If found, it asks for confirmation before using the detected key.
    - If not found or you decline confirmation, it prompts you to enter your key securely.
    - You will be asked to choose a model from a list (e.g., `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`) using an interactive menu.

3.  **View current configuration:**
    ```bash
    python main.py setup view
    ```

Your configuration is saved in `~/.ai-cli/config/config.json`.

## Usage

All commands are run via the `main.py` script.

### Interactive Sessions (`session` commands)

- **Start New:**
  - `python main.py session new` (Auto-named)
  - `python main.py session new --name "my-session"` (User-named)
- **Resume Session:**
  - `python main.py session resume` (Interactive list)
- **List Sessions:**
  - `python main.py session list` (Sorted list)
- **Delete Sessions:**
  - `python main.py session delete` (Interactive multi-select)

### Direct Prompting (`prompt` command)

- **Basic Prompt:**
  ```bash
  python main.py prompt "Translate 'hello world' to French"
  ```
- **With Piped Data:**
  ```bash
  cat code.py | python main.py prompt "Explain this Python code"
  ```
- **With File Context:**
  ```bash
  python main.py prompt "Summarize this document" --file report.txt
  # Note: If both stdin and --file are used, stdin takes precedence.
  ```
- **Specify Output Format:**

  ```bash
  # Get raw text output
  python main.py prompt "Generate a list of colors" --output-format raw

  # Attempt to get JSON output
  python main.py prompt "Info for London: population, timezone as JSON" -of json
  ```

- **Save Output to File:**

  ```bash
  python main.py prompt "Write a Dockerfile for a basic Python app" -o Dockerfile

  # Combine with other options
  cat data.json | python main.py prompt "Convert this to YAML" -of raw -o data.yaml
  ```

### In-Chat Commands (during `session new` or `session resume`)

- `/help`: Show commands.
- `/rename <new-name>`: Rename session.
- `/history`: Show conversation.
- `/clear`: Clear conversation history (requires confirmation).
- `/upload [path]`: Stage file(s) for next prompt (use path or `fzf`).
- `/edit`: Open `$EDITOR` for multi-line input.
- `/status`: Show staged files.
- `/clearfiles`: Remove all staged files.
- `/exit` or `/quit`: Exit session.

## Session Storage

Chat session history is stored as JSON files in the `~/.ai-cli/chat_sessions/` directory using the pattern `session-display-name_uniqueID.json`.

## Contributing (Optional Placeholder)

Contributions are welcome! Please follow standard fork/branch/PR procedures.

## License (Optional Placeholder)

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
