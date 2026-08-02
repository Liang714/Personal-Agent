import functools
import sys
from pathlib import Path

import click

from agent import config
from agent.errors import AgentError
from agent.storage.db import init_db


def handle_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except AgentError as exc:
            click.secho(f"Error: {exc}", fg="red", err=True)
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            click.secho(f"Unexpected error: {exc}", fg="red", err=True)
            sys.exit(1)

    return wrapper


@click.group()
def cli():
    try:
        config.ensure_dirs()
        init_db()
    except OSError as exc:
        click.secho(f"Startup error: {exc}", fg="red", err=True)
        sys.exit(1)


@cli.command()
@click.argument("message")
@handle_errors
def chat(message: str):
    from agent.core.agent_loop import ask

    click.echo(ask(message))


@cli.command()
@click.argument("audio_path", type=click.Path(exists=True, path_type=Path))
@handle_errors
def memo(audio_path: Path):
    from agent.capabilities.memos import handle_memo_file

    result = handle_memo_file(audio_path)

    click.echo(f"Transcript:\n{result['transcript']}\n")

    if result["tasks"]:
        click.echo("Tasks extracted:")
        for task_id, task in zip(result["task_ids"], result["tasks"]):
            click.echo(f"  [{task_id}] {task}")
    else:
        click.echo("Tasks extracted: none")

    if result["journal_path"]:
        click.echo(f"\nJournal entry appended to {result['journal_path']}")
    else:
        click.echo("\nNo journal-worthy content found.")


@cli.group()
def auth():
    pass


@auth.command()
@handle_errors
def setup():
    from agent.google_auth import run_setup_flow

    run_setup_flow()
    click.echo("Google auth complete. Token saved.")


@cli.group()
def inbox():
    pass


@inbox.command()
@handle_errors
def scan():
    from agent.core.agent_loop import ask

    click.echo(
        ask(
            "Scan my unread inbox using scan_inbox. For each email, decide if it needs attention "
            "and say why. For any email that clearly needs a reply, look up its full content with "
            "get_message and draft a reply with draft_reply — do not ask for permission first, "
            "drafts are always safe since they are never sent automatically. Summarize what you "
            "found and what you drafted."
        )
    )


@inbox.command()
@click.argument("message_id")
@handle_errors
def draft(message_id: str):
    from agent.core.agent_loop import ask

    click.echo(ask(f"Look up email {message_id} with get_message, then draft an appropriate reply with draft_reply."))


@cli.group()
def calendar():
    pass


@calendar.command()
@handle_errors
def today():
    from agent.core.agent_loop import ask

    click.echo(ask("What's on my calendar today? Use list_today_events. Flag any conflicts or back-to-back meetings."))


if __name__ == "__main__":
    cli()
