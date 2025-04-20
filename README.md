# AI Assistant CLI

A powerful and user-friendly command-line interface (CLI) to interact with OpenAI's chat models (like GPT-3.5, GPT-4, GPT-4o). Built with Python using Typer, Rich, Questionary, and the OpenAI library.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) <!-- Choose your license -->

## Overview

This CLI provides a seamless way to chat with AI models directly from your terminal. It supports persistent chat sessions, allowing you to resume conversations later. It features automatic session naming based on your first prompt, interactive menus for resuming and deleting sessions, beautiful Markdown rendering for responses (including code syntax highlighting), and helpful in-chat commands.

## Features

- **Interactive Chat:** Engage in conversation with OpenAI models.
- **Persistent Sessions:** Automatically saves chat history.
  - **Resume:** Pick up previous conversations exactly where you left off.
  - **List:** View all saved chat sessions.
  - **Delete:** Interactively select and delete unwanted sessions.
- **Automatic Session Naming:** If you don't provide a name, the CLI uses AI to generate a relevant name based on your first message.
- **User-Defined Session Names:** Optionally name your sessions for better organization.
- **Rich Output:** AI responses are rendered using Markdown for better readability:
  - Headings, lists, bold, italics, etc.
  - Syntax highlighting for code blocks (`python ... `).
- **Loading Indicator:** Shows a spinner animation while waiting for the AI response.
- **In-Chat Commands:** Manage your session on the fly:
  - `/help`: Show available commands.
  - `/rename <new-name>`: Rename the current session.
  - `/history`: Display the conversation history so far.
  - `/clear`: Clear the history for the current session (irreversible!).
  - `/exit` or `/quit`: End the current chat session.
- **Secure Configuration:** Interactively set up your OpenAI API key and preferred model. Configuration is stored locally.

## Installation

**Prerequisites:**

- Python 3.8 or higher.
- `pip` (Python package installer).
- An OpenAI account and API key. ([Get one here](https://platform.openai.com/signup))

**Steps:**

1.  **Clone the repository:**

    ```bash
    git clone <your-repository-url> # Replace with your repo URL
    cd <repository-directory>
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
    _(Alternatively, if you create a `requirements.txt` file with the above packages listed, you can run `pip install -r requirements.txt`)_

## Configuration

Before you can start chatting, you need to configure your OpenAI API key and choose a default model.

1.  **Run the setup command:**

    ```bash
    python main.py setup configure
    ```

2.  **Follow the prompts:**

    - You will be asked to enter your OpenAI API key.
    - You will be asked to choose a model from a list (e.g., `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo`).

3.  **Alternatively, provide options directly (less secure for API key):**

    ```bash
    python main.py setup configure --openai-api-key "sk-..." --model "gpt-4o"
    ```

4.  **View current configuration:**
    To see your currently saved settings (API key will be partially masked):
    ```bash
    python main.py setup view
    ```

Your configuration is saved securely in `~/.ai-cli/config/config.json`.

## Usage

All commands are run via the `main.py` script.

### Starting a New Chat

- **With automatic naming:** The session will be named based on your first prompt.

  ```bash
  python main.py chat new
  ```

  After you enter your first message, the CLI will generate and assign a name (e.g., `discuss-python-features_a1b2c3d4`).

- **With a specific name:**
  ```bash
  python main.py chat new --name "my-project-ideas"
  ```
  This will create a session named `my-project-ideas` (with a unique ID suffix, e.g., `my-project-ideas_e5f6a7b8`).

### Resuming a Chat

This command lists your saved sessions interactively. Use arrow keys to select and Enter to resume.

```bash
python main.py chat resume
```

### Listing Sessions

To see a non-interactive list of all saved session display names:

```bash
python main.py chat list
```

### Deleting a Chat

This command lists your saved sessions interactively. Select the session you want to delete and confirm.

```bash
python main.py chat delete
```

### In-Chat Commands

While inside an active chat session, type these commands instead of a regular message:

- `/help`: Shows this list of in-chat commands.
- `/rename <new-name>`: Renames the current session. Example: `/rename python-debugging`
- `/history`: Prints the conversation history loaded in the current session.
- `/clear`: Asks for confirmation, then clears all messages from the current session file. **Use with caution!**
- `/exit` or `/quit`: Saves the current session and exits the chat interaction loop.

## Session Storage

Chat session history is stored as JSON files in the `~/.ai-cli/chat_sessions/` directory. Each file is named using the pattern `session-display-name_uniqueID.json`. The unique ID ensures that even if multiple sessions get the same automatically generated name, their files remain distinct. The listing, resuming, and deleting commands primarily show the `session-display-name` part for user-friendliness.

## Contributing (Optional Placeholder)

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/your-feature`).
3.  Make your changes.
4.  Commit your changes (`git commit -am 'Add some feature'`).
5.  Push to the branch (`git push origin feature/your-feature`).
6.  Create a new Pull Request.

## License (Optional Placeholder)

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. (You'll need to create a LICENSE file if you choose one).
