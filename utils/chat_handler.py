import uuid

from openai import OpenAI

from utils.session_handler import (
    create_session,
    load_session_messages,
    rename_session,
    save_message,
)


# Function to display help information
def show_help():
    print("[bold green]Available Commands:[/bold green]")
    print("[bold blue]/rename [new_name][/bold blue] - Rename the current session")
    print("[bold blue]/help[/bold blue] - List all available commands and information")
    print(
        "[bold blue]exit[/bold blue] or [bold blue]quit[/bold blue] - End the chat session"
    )


# Helper function to start a new chat session
def start_new_chat(config, session_name):
    client = OpenAI(api_key=config["openai_api_key"])
    model = config["model"]

    # Use provided session name or generate a random one
    session_id = session_name or str(uuid.uuid4())[:8]
    create_session(session_id)

    print("[bold blue]Type '/help' for a list of commands[/bold blue]")
    print(
        f"[bold green]🧠 New chat session started! Session ID: {session_id}[/bold green]"
    )
    print("[bold blue]Type '/exit' to end the session[/bold blue]")
    print(
        "[bold yellow]💡Tip: Rename this session anytime with '/rename your_session_name'[/bold yellow]"
    )

    return client, model, session_id


# Function to handle message exchange and session saving
def handle_messages(client, model, session_id, messages):
    while True:
        print("[bold cyan]You[/bold cyan]: ", end="")
        user_input = input().strip()

        if user_input.lower() in ["/exit", "/quit"]:
            if not messages:
                print(
                    "[bold yellow]No messages exchanged, session discarded.[/bold yellow]"
                )
                break
            save_message(session_id, "user", "exit")
            break

        if user_input == "/help":
            show_help()
            continue
        if user_input.startswith("/rename"):
            new_name = user_input[len("/rename ") :].strip()
            try:
                success = rename_session(session_id, new_name)
                if success:
                    print(f"[bold green]✅ Session renamed to: {new_name}[/bold green]")
                    session_id = new_name
                    continue
            except FileExistsError as fe:
                print(f"[bold red]❌ {fe}[/bold red]")
                continue
            except Exception as e:
                print(f"[bold red]❌ Rename failed: {e}[/bold red]")
                continue

        if user_input:
            messages.append({"role": "user", "content": user_input})
            save_message(session_id, "user", user_input)

            try:
                print("[bold green]AI:[/bold green] ", end="")

                response = client.chat.completions.create(
                    model=model,
                    messages=load_session_messages(session_id),
                    temperature=0.7,
                )
                reply = response.choices[0].message.content

                print(reply)
                print()
                messages.append({"role": "assistant", "content": reply})
                save_message(session_id, "assistant", reply)
            except Exception as e:
                print(f"[bold red]❌ Error:[/bold red] {e}")
                break
