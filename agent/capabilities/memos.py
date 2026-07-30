from datetime import date
from pathlib import Path

from pydantic import BaseModel

from agent import config
from agent.llm_client import client
from agent.storage import db, files
from agent.stt.transcribe import transcribe

MEMO_PROMPT = """The following is a raw transcript of a rambling voice memo. Split it into:
- concrete action items / todos (short imperative phrases)
- reflective / journal-worthy content (thoughts, feelings, observations that aren't tasks)

Some transcripts will have only tasks, only journal content, or both. Don't invent content \
that isn't in the transcript.

Transcript:
{transcript}"""


class MemoExtraction(BaseModel):
    tasks: list[str]
    journal_entry: str


def process_memo(transcript: str) -> MemoExtraction:
    response = client.chat(
        model=config.OLLAMA_MODEL,
        messages=[{"role": "user", "content": MEMO_PROMPT.format(transcript=transcript)}],
        format=MemoExtraction.model_json_schema(),
    )
    return MemoExtraction.model_validate_json(response.message.content)


def handle_memo_file(audio_path: Path) -> dict:
    transcript = transcribe(audio_path)
    extraction = process_memo(transcript)

    task_ids = [db.add_task(t, source=f"memo:{audio_path.name}") for t in extraction.tasks]

    journal_path = None
    if extraction.journal_entry.strip():
        entry_date = date.today()
        journal_path = files.append_journal_entry(entry_date, extraction.journal_entry)
        db.add_journal_index(entry_date.isoformat(), journal_path, source=f"memo:{audio_path.name}")

    return {
        "transcript": transcript,
        "tasks": extraction.tasks,
        "task_ids": task_ids,
        "journal_entry": extraction.journal_entry,
        "journal_path": journal_path,
    }
