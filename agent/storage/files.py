from datetime import date

from agent import config


def append_journal_entry(entry_date: date, text: str) -> str:
    path = config.JOURNAL_DIR / f"{entry_date.isoformat()}.md"
    timestamp = entry_date.isoformat()
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {timestamp}\n\n{text.strip()}\n")
    return str(path)
