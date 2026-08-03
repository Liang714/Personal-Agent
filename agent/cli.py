import functools
import logging
import sys
from pathlib import Path

import click

from agent import config
from agent.errors import AgentError
from agent.logging_config import setup_logging
from agent.storage.db import init_db

log = logging.getLogger(__name__)


def handle_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except AgentError as exc:
            log.warning("%s failed: %s", fn.__name__, exc)
            click.secho(f"Error: {exc}", fg="red", err=True)
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            log.exception("%s failed unexpectedly", fn.__name__)
            click.secho(f"Unexpected error: {exc}", fg="red", err=True)
            sys.exit(1)

    return wrapper


@click.group()
def cli():
    try:
        config.ensure_dirs()
        setup_logging()
        init_db()
    except OSError as exc:
        click.secho(f"Startup error: {exc}", fg="red", err=True)
        sys.exit(1)


@cli.command()
@click.argument("message", required=False)
@handle_errors
def chat(message: str | None):
    from agent.capabilities.companion import load_recent_history, save_turn
    from agent.core.agent_loop import ask

    if message:
        history = load_recent_history()
        response = ask(message, history=history)
        save_turn("user", message)
        save_turn("assistant", response)
        click.echo(response)
        return

    click.echo("Chat session started. Type 'exit' or Ctrl+D to quit.")
    history = load_recent_history()
    while True:
        try:
            user_input = click.prompt("You", prompt_suffix="> ")
        except (click.exceptions.Abort, EOFError):
            click.echo("\nBye.")
            break
        if user_input.strip().lower() in ("exit", "quit"):
            click.echo("Bye.")
            break

        response = ask(user_input, history=history)
        click.echo(f"Agent> {response}")
        save_turn("user", user_input)
        save_turn("assistant", response)
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})
        history = history[-10:]  # keep bounded, same window as load_recent_history()'s default


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
@click.option("--dry-run", is_flag=True, help="Triage only — don't actually create any drafts.")
@handle_errors
def scan(dry_run: bool):
    from agent.capabilities.inbox import run_scan_and_draft

    click.echo(run_scan_and_draft(dry_run=dry_run))


@inbox.command()
@click.argument("message_id")
@handle_errors
def draft(message_id: str):
    from agent.core.agent_loop import ask

    click.echo(ask(f"Look up email {message_id} with get_message, then draft an appropriate reply with draft_reply."))


@inbox.command()
@click.option("--interval", default=None, type=int, help="Minutes between scans (default: config.INBOX_SCAN_INTERVAL_MINUTES).")
def daemon(interval: int | None):
    """Run inbox scan on a repeating schedule until interrupted (Ctrl+C)."""
    from apscheduler.schedulers.blocking import BlockingScheduler

    from agent.capabilities.inbox import run_scan_and_draft

    setup_logging()
    minutes = interval or config.INBOX_SCAN_INTERVAL_MINUTES

    def _run_scan():
        log.info("Running scheduled inbox scan")
        try:
            result = run_scan_and_draft()
            log.info("Scheduled inbox scan complete:\n%s", result)
        except AgentError as exc:
            log.warning("Scheduled inbox scan failed: %s", exc)
        except Exception:  # noqa: BLE001
            log.exception("Scheduled inbox scan failed unexpectedly")

    click.echo(f"Starting inbox scan daemon — every {minutes} minute(s). Ctrl+C to stop.")
    scheduler = BlockingScheduler()
    scheduler.add_job(_run_scan, "interval", minutes=minutes, next_run_time=None)
    _run_scan()  # run once immediately, then on the schedule
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        click.echo("Daemon stopped.")


@cli.group()
def calendar():
    pass


@calendar.command()
@handle_errors
def today():
    from agent.core.agent_loop import ask

    click.echo(ask("What's on my calendar today? Use list_events_on_date. Flag any conflicts or back-to-back meetings."))


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
def serve(host: str, port: int):
    import uvicorn

    uvicorn.run("agent.api.main:app", host=host, port=port)


if __name__ == "__main__":
    cli()
