import typer
from openai import OpenAI
from rich import print
from utils.chat_handler import handle_messages, start_new_chat
from utils.config_handler import check_config, load_config
from utils.session_handler import list_sessions, load_session_messages

app = typer.Typer()


@app.command("new")
def new_chat(
    session_name: str = typer.Option(
        None, "--session-name", "-s", help="Optional name for the chat session"
    )
):
    """Start a new chat session"""
    config = load_config()
    check_config(config)

    client, model, session_id = start_new_chat(config, session_name)
    messages = []
    handle_messages(client, model, session_id, messages)


@app.command("resume")
def resume_chat(session_id: str = typer.Argument(..., help="Session ID to resume")):
    """Resume a previous chat session"""
    config = load_config()
    check_config(config)

    client = OpenAI(api_key=config["openai_api_key"])
    model = config["model"]

    try:
        messages = load_session_messages(session_id)
    except FileNotFoundError:
        print(f"[bold red]❌ Session '{session_id}' not found.[/bold red]")
        raise typer.Exit()

    print(f"[bold green]🔄 Resuming session: {session_id}[/bold green]")
    print("[bold blue]Type 'exit' to end the session[/bold blue]")

    handle_messages(client, model, session_id, messages)


@app.command("list")
def list_all_sessions():
    """List all saved chat sessions"""
    sessions = list_sessions()
    if not sessions:
        print("[yellow]No sessions found.[/yellow]")
    else:
        print("[bold green]Saved sessions:[/bold green]")
        for session_id in sessions:
            print(f" - {session_id}")
