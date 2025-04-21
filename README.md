# AI CLI - Multi-Provider AI Assistant

A powerful and user-friendly command-line interface (CLI) to interact with various AI models, including **OpenAI (GPT-3.5, GPT-4, GPT-4o)** and **Google Gemini (Gemini Pro, Gemini Flash)**. Built with Python using Typer, Rich, Questionary, and official provider libraries.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Choose your license -->

<!-- Add other badges if desired (e.g., build status, coverage) -->

## Overview

This CLI provides a seamless way to interact with Large Language Models (LLMs) directly from your terminal. It supports both interactive chat sessions with persistent history and direct non-interactive prompting across multiple AI providers.

**Interactive Sessions:** Start, resume, list, and delete persistent chat sessions. Features include automatic session naming, rich Markdown rendering for AI responses, file uploads with relative path context (enhanced with optional `fzf`/`fd`/`bat`/`eza` integration), token usage estimates, and various in-chat commands (including editing multi-line input via your preferred `$EDITOR`). You can specify providers/models per session or rely on configured defaults.

**Direct Prompting:** Get quick answers or generate content without entering an interactive session. Supports piping data via `stdin`, providing file context, choosing output formats (Markdown, raw text, JSON), saving results directly to files, and explicitly specifying the AI provider and model for the request. Token usage information is displayed on stderr after execution.

## Features

- **Multi-Provider Support:** Seamlessly switch between different AI services (initially OpenAI & Google Gemini). Easily extendable.
- **Flexible Configuration (`setup` command):**
  - Interactively configure API keys and select default models for each supported provider (`setup configure`).
  - Set a global default provider to use when none is specified (`setup set-default`).
  - View the current configuration, including masked API keys (`setup view`).
  - Reads provider API keys from environment variables (`OPENAI_API_KEY`, `GOOGLE_API_KEY`) or prompts securely if not found.
  - Configuration stored locally in `~/.ai-cli/config/config.json`.
- **Interactive Chat Sessions (`session` command):**
  - Start new sessions (`session new`), optionally named (`--name`) or automatically named based on the first prompt. Specify provider/model with `--provider`/`--model` to override defaults for that session.
  - Resume previous sessions via an interactive list (`session resume`). Can also override provider/model when resuming.
  - List all saved sessions (`session list`), sorted by modification time (latest first).
  - Delete one or more sessions via an interactive checklist (`session delete`).
  - Persistent message history saved for each session in `~/.ai-cli/chat_sessions/`.
- **Direct Prompting (`prompt` command):**
  - Send a single prompt directly: `ai-cli prompt "Your question"`
  - Specify provider/model: `ai-cli prompt "Ask Google..." --provider google`
  - **Pipe `stdin`:** Process piped data: `cat file.txt | ai-cli prompt "Summarize:"`
  - **File Context:** Provide a file as context: `ai-cli prompt "Explain code" -f script.py` (Note: `stdin` takes precedence over `-f`).
  - **Output Formats:** Choose output: `markdown` (default), `raw`, `json` using `--output-format` or `-of`.
  - **Save to File:** Save the response directly: `ai-cli prompt "Generate code" -o code.py`
  - **Token Usage:** Displays estimated token usage (prompt, completion, total) on stderr after completion.
- **Rich Output:** AI responses rendered using Markdown (default) for enhanced readability, including syntax highlighting for code blocks.
- **File Handling (Interactive Session):**
  - Stage one or more files using `/upload [path]` or just `/upload` (requires `fzf` and `fd` for interactive picker).
  - Files are included with relative path context in the prompt sent to the AI.
  - File preview within `fzf` enhanced by optional `bat` (syntax highlighting) and `eza` (tree view for directories).
  - Check pending files (with relative paths) using `/status`.
  - Clear all pending files before sending with `/clearfiles`.
  - Prevents adding the exact same absolute file path multiple times.
  - Configurable max file size (default: 50KB) and allowed extensions (defined in `constants.py`).
- **External Editor Support (Interactive Session):**
  - Use the `/edit` command to open your default editor (specified by `$EDITOR`) for composing multi-line input comfortably.
- **In-Chat Commands (Interactive Session):**
  - `/help`: Show available commands (nicely formatted).
  - `/rename <new-name>`: Rename the current session file.
  - `/history`: Display the conversation history for the current session.
  - `/clear`: Clear the history for the current session (requires confirmation).
  - `/upload [path]`: Stage a file to be included in the next prompt.
  - `/edit`: Open `$EDITOR` for multi-line input.
  - `/status`: View staged files and their sizes.
  - `/clearfiles`: Remove all staged files without sending.
  - `/usage`: Show estimated token usage accumulated in the current session instance.
  - `/exit` or `/quit`: End the current chat session.

## Installation

**Prerequisites:**

- **Required:**
  - Python 3.8 or higher.
  - `pip` (Python package installer).
  - API keys for the desired AI providers (e.g., OpenAI, Google AI).
    - [Get OpenAI Key](https://platform.openai.com/signup)
    - [Get Google AI Key](https://aistudio.google.com/app/apikey)
- **Optional (Highly Recommended for Enhanced Features):**
  - `fzf`: For interactive file selection with `/upload`. ([Install Instructions](#installing-optional-dependencies))
  - `fd`: Used by `fzf` integration for fast file searching. ([Install Instructions](#installing-optional-dependencies))
  - `bat`: Provides syntax highlighting in `fzf` file previews. ([Install Instructions](#installing-optional-dependencies))
  - `eza`: Provides tree view previews for directories in `fzf`. ([Install Instructions](#installing-optional-dependencies))
  - A configured `$EDITOR` environment variable (e.g., `vim`, `nano`, `code`) for the `/edit` command.

**Installation Command:**

```bash
pip install ai-assistant-multi
```

## Installing Optional Dependencies

These tools significantly enhance the interactive experience. Install them using your system's package manager.

- **`fzf` (Fuzzy Finder):**

  - macOS: `brew install fzf`
  - Debian/Ubuntu: `sudo apt update && sudo apt install fzf`
  - Fedora: `sudo dnf install fzf`
  - Arch: `sudo pacman -S fzf`
  - Windows (Scoop): `scoop install fzf` | (Choco): `choco install fzf`
  - [fzf GitHub](https://github.com/junegunn/fzf#installation)

- **`fd` (fd-find - A simple, fast and user-friendly alternative to 'find'):**

  - macOS: `brew install fd`
  - Debian/Ubuntu: `sudo apt update && sudo apt install fd-find` (Note: May install as `fdfind`. If so, symlink: `ln -s $(which fdfind) ~/.local/bin/fd`)
  - Fedora: `sudo dnf install fd-find`
  - Arch: `sudo pacman -S fd`
  - Windows (Scoop): `scoop install fd` | (Choco): `choco install fd`
  - [fd GitHub](https://github.com/sharkdp/fd#installation)

- **`bat` (Cat clone with syntax highlighting):**

  - macOS: `brew install bat`
  - Debian/Ubuntu: `sudo apt update && sudo apt install bat` (Note: May install as `batcat`. If so, symlink: `ln -s $(which batcat) ~/.local/bin/bat`)
  - Fedora: `sudo dnf install bat`
  - Arch: `sudo pacman -S bat`
  - Windows (Scoop): `scoop install bat` | (Choco): `choco install bat`
  - [bat GitHub](https://github.com/sharkdp/bat#installation)

- **`eza` (Modern replacement for ls):**

  - macOS: `brew install eza`
  - Debian/Ubuntu/Fedora/Arch: Check package managers or install from [eza GitHub](https://github.com/eza-community/eza#installation) (binaries/cargo recommended).
  - Windows (Scoop): `scoop install eza` | (Choco): `choco install eza`

- **`$EDITOR` Environment Variable:**
  Ensure your system's `$EDITOR` environment variable is set to your preferred command-line text editor. Add this to your shell configuration file (e.g., `.bashrc`, `.zshrc`, `.profile`):
  ```bash
  export EDITOR=vim # Or nano, emacs, micro, helix, etc.
  ```

Reload your shell or run `source ~/.your_shell_rc_file` for the change to take effect.

## Configuration

Before using the CLI, configure the AI providers you want to interact with.

1.  **Run the interactive configuration:**

    ```bash
    # If you created a link/alias:
    ai-cli setup configure
    # Or directly:
    python main.py setup configure
    ```

2.  **Follow the prompts:**

    - Select the providers (OpenAI, Google, etc.) you wish to set up.
    - For each selected provider:
      - The tool checks for existing API keys in environment variables (e.g., `OPENAI_API_KEY`) or the current config file.
      - If a key is found, you'll be asked to confirm or update it (input is hidden).
      - If no key is found, you'll be prompted to enter it securely.
      - You'll select a default model for that provider from a list.
    - If multiple providers are configured, you'll be asked to choose a **global default provider**. This provider will be used when you don't explicitly specify one using the `--provider` flag.

3.  **Set/Change the Default Provider Later (Optional):**

    ```bash
    ai-cli setup set-default
    ```

4.  **View Current Configuration:**
    ```bash
    ai-cli setup view
    ```

Your settings are saved in `~/.ai-cli/config/config.json`.

## Usage

Replace `python main.py` with your alias (e.g., `ai-cli`) if you set one up.

### Interactive Sessions (`session` commands)

- **Start New (using default provider):**
  ```bash
  ai-cli session new
  ai-cli session new --name "my-analysis"
  ```
- **Start New (specifying provider/model):**
  ```bash
  ai-cli session new --provider google --model gemini-1.5-flash-latest
  ai-cli session new -p openai -m gpt-4o --name "gpt4o-chat"
  ```
- **Resume Session (select from list):**
  ```bash
  ai-cli session resume
  # Resume but override the provider for this specific session run
  ai-cli session resume --provider openai
  ```
- **List Sessions:**
  ```bash
  ai-cli session list
  ```
- **Delete Sessions (select from list):**
  ```bash
  ai-cli session delete
  ```

### Direct Prompting (`prompt` command)

- **Basic Prompt (using default provider):**
  ```bash
  ai-cli prompt "What are the main benefits of using Python?"
  ```
- **Specify Provider/Model:**
  ```bash
  ai-cli prompt "What's the weather like on Mars?" -p google
  ai-cli prompt "Write a short Rust function for bubble sort" -p openai -m gpt-4o
  ```
- **Using Piped Data (`stdin`):**
  ```bash
  cat data.csv | ai-cli prompt "Find the average value in the second column"
  git diff | ai-cli prompt "Summarize these code changes" -p openai
  ```
- **Using File Context (`-f`):**
  ```bash
  ai-cli prompt "Refactor this code for better readability" -f my_script.py
  # Note: If stdin is piped, the --file argument is ignored.
  ```
- **Specify Output Format (`-of`):**

  ```bash
  # Get raw text output
  ai-cli prompt "Generate five catchy taglines for a coffee shop" -of raw

  # Attempt to get JSON output
  ai-cli prompt "List the planets and their diameters as a JSON object" -of json -p google
  ```

- **Save Output to File (`-o`):**

  ```bash
  ai-cli prompt "Write a Python script to list files in a directory" -p openai -o list_files.py

  # Combine with other options (e.g., raw output to file)
  cat report.md | ai-cli prompt "Extract all action items into a bulleted list" -of raw -o action_items.txt
  ```

### In-Chat Commands (during `session new` or `session resume`)

Type these commands directly into the chat prompt:

- `/help`: Show this list of commands.
- `/rename <new-name>`: Change the name of the current session.
- `/history`: Display the conversation history.
- `/clear`: Clear the conversation history (irreversible!).
- `/upload [path]`: Stage a file. If `path` is omitted, attempts interactive selection (requires `fzf`, `fd`).
- `/edit`: Open your `$EDITOR` for multi-line input.
- `/status`: View files currently staged for the next prompt.
- `/clearfiles`: Remove all staged files.
- `/usage`: Show the estimated token count for the current session instance.
- `/exit` or `/quit`: End the chat session.

## Storage Locations

- **Configuration File:** `~/.ai-cli/config/config.json`
- **Session History Files:** `~/.ai-cli/chat_sessions/` (Each session stored as `session-name_uuid.json`)

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs, feature requests, or improvements.

_(Optionally add more specific contribution guidelines here: e.g., coding style, testing requirements)_

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```

```
