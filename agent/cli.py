from pathlib import Path

import click

from agent.storage.db import init_db


@click.group()
def cli():
    init_db()


@cli.command()
@click.argument("message")
def chat(message: str):
    from agent.core.agent_loop import ask

    click.echo(ask(message))


@cli.command()
@click.argument("audio_path", type=click.Path(exists=True, path_type=Path))
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


if __name__ == "__main__":
    cli()
