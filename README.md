# AI Assistant CLI

AI Assistant CLI is a command-line interface tool designed to manage and interact with AI-driven chat sessions. It provides functionalities to create, save, and manage chat sessions, making it easier to maintain conversation history and configurations.

## Project Structure

- **main.py**: The entry point of the application. It initializes the CLI and handles user inputs.
- **commands/**: Contains command definitions for the CLI.
  - `chat.py`: Manages chat-related commands.
  - `setup.py`: Handles setup and configuration commands.
- **utils/**: Utility modules for handling various functionalities.
  - `chat_handler.py`: Manages chat operations and interactions.
  - `config_handler.py`: Handles configuration settings and operations.
  - `session_handler.py`: Manages session creation, renaming, and message storage.

## Setup

1. **Clone the repository**:

   ```bash
   # for SSH
   git clone git@github.com:Sudharshan1409/ai-cli.git
   cd ai-cli

   # for HTTPS
   git clone https://github.com/Sudharshan1409/ai-cli.git
   cd ai-cli
   ```

2. **Install dependencies**:

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   python main.py
   ```

## Usage

### Commands

- **new**: Start a new chat session.

  - **Options**:
    - `--session-name`, `-s`: Optional name for the chat session.
  - **Description**: This command initializes a new chat session. You can optionally provide a session name to better organize your sessions.

- **resume**: Resume a previous chat session.

  - **Arguments**:
    - `session_id`: The ID of the session you want to resume.
  - **Description**: This command allows you to continue a chat session from where you left off by providing the session ID.

- **Create a new session**: Use the CLI to start a new chat session.
- **Save messages**: Messages are automatically saved to the session file.
- **List sessions**: View all saved sessions using the list command.
- **Rename sessions**: Rename existing sessions for better organization.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License.
