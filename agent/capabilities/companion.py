import sqlite3

from pydantic import BaseModel, ValidationError

from agent import config
from agent.core.tools import register_tool
from agent.errors import MatchExtractionError
from agent.llm_client import client
from agent.storage import db


def load_recent_history(limit: int = 10) -> list[dict]:
    rows = db.get_recent_conversation(limit=limit)
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def save_turn(role: str, content: str) -> None:
    db.add_conversation_turn(role, content)


@register_tool
def list_recent_tasks() -> str:
    """List the user's open tasks (extracted from voice memos or other sources)."""
    rows = db.list_open_tasks()
    if not rows:
        return "No open tasks."
    return "\n".join(f"[{r['id']}] {r['description']} (from {r['source']})" for r in rows[:15])


def complete_task(task_id: int) -> str:
    """Mark a task as done by id."""
    db.mark_task_done(task_id)
    return f"Task {task_id} marked done."


def delete_task(task_id: int) -> str:
    """Delete a task by id."""
    db.delete_task(task_id)
    return f"Task {task_id} deleted."


class _MatchedTaskIds(BaseModel):
    task_ids: list[int]
    explanation: str


_TASK_MATCH_PROMPT = """Here is the user's real list of open tasks (id, description, source). \
A user asked to {action} task(s) matching this description: "{description}"

Open tasks:
{listing}

Return the id(s) of the task(s) that match. If it clearly refers to one task, return just that \
one id. If it refers to multiple (e.g. "both", "all of them"), return all matching ids. If \
you're not confident anything matches, return an empty list — never guess or invent an id that \
isn't in the list above."""


def _match_task_ids(description: str, action: str, tasks: list[sqlite3.Row]) -> list[int]:
    listing = "\n".join(f"[{r['id']}] {r['description']} (from {r['source']})" for r in tasks)
    response = client.chat(
        model=config.OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": _TASK_MATCH_PROMPT.format(action=action, description=description, listing=listing),
            }
        ],
        format=_MatchedTaskIds.model_json_schema(),
    )
    content = response.message.content
    if not content:
        raise MatchExtractionError("The model returned no content while matching the task description.")
    try:
        matched = _MatchedTaskIds.model_validate_json(content)
    except ValidationError as exc:
        raise MatchExtractionError(f"Couldn't parse the model's match output: {exc}") from exc

    real_ids = {r["id"] for r in tasks}
    return [tid for tid in matched.task_ids if tid in real_ids]


def _resolve_matching_tasks(description: str, action: str) -> tuple[list[sqlite3.Row], list[int], str | None]:
    """Fetch real open tasks and match description against them.

    Returns (tasks, matched_ids, early_return_message). If early_return_message is not None,
    callers should return it as-is.
    """
    tasks = db.list_open_tasks()
    if not tasks:
        return tasks, [], "No open tasks."

    matched_ids = _match_task_ids(description, action, tasks)
    if not matched_ids:
        listing = "\n".join(f"[{r['id']}] {r['description']} (from {r['source']})" for r in tasks)
        return (
            tasks,
            [],
            f'Couldn\'t confidently match "{description}" to any open task — nothing was '
            f"changed. Open tasks:\n{listing}",
        )
    return tasks, matched_ids, None


@register_tool
def complete_tasks(description: str) -> str:
    """Mark one or more open tasks as done, matched from a natural-language description (e.g.
    "the plants task", "both the bank and grocery ones"). Do not invent or guess a task id
    yourself — pass the user's own description and this tool will look up the real open tasks
    and match against them itself."""
    tasks, matched_ids, message = _resolve_matching_tasks(description, "complete")
    if message:
        return message
    by_id = {r["id"]: r for r in tasks}
    for tid in matched_ids:
        complete_task(tid)
    lines = [f"Marked {len(matched_ids)} task(s) done:"]
    lines += [f"  - {by_id[tid]['description']}" for tid in matched_ids]
    return "\n".join(lines)


@register_tool
def delete_tasks(description: str) -> str:
    """Delete one or more open tasks, matched from a natural-language description (e.g. "the
    plants task", "both the bank and grocery ones"). Do not invent or guess a task id yourself —
    pass the user's own description and this tool will look up the real open tasks and match
    against them itself."""
    tasks, matched_ids, message = _resolve_matching_tasks(description, "delete")
    if message:
        return message
    by_id = {r["id"]: r for r in tasks}
    for tid in matched_ids:
        delete_task(tid)
    lines = [f"Deleted {len(matched_ids)} task(s):"]
    lines += [f"  - {by_id[tid]['description']}" for tid in matched_ids]
    return "\n".join(lines)


@register_tool
def search_journal(keyword: str) -> str:
    """Search past journal entries for a keyword and return matching entries."""
    matches = []
    for path in sorted(config.JOURNAL_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if keyword.lower() in text.lower():
            matches.append(f"--- {path.name} ---\n{text.strip()}")
    if not matches:
        return f"No journal entries found mentioning '{keyword}'."
    return "\n\n".join(matches[:5])
