import typer

from commands import chat, setup

app = typer.Typer()
app.add_typer(setup.app)
app.add_typer(chat.app, name="chat", help="Create or Resume a session and chat with AI")

if __name__ == "__main__":
    app()
