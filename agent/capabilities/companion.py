from agent import config
from agent.core.tools import register_tool
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


@register_tool
def complete_task(task_id: int) -> str:
    """Mark a task as done by id. Use list_recent_tasks first to find the task's id."""
    db.mark_task_done(task_id)
    return f"Task {task_id} marked done."


@register_tool
def delete_task(task_id: int) -> str:
    """Delete a task by id. Use list_recent_tasks first to find the task's id."""
    db.delete_task(task_id)
    return f"Task {task_id} deleted."


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
