import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
MEMOS_WATCH_DIR = Path(os.environ.get("MEMOS_WATCH_DIR", DATA_DIR / "memos"))
JOURNAL_DIR = DATA_DIR / "journal"
DB_PATH = DATA_DIR / "agent.db"

GOOGLE_CREDENTIALS_PATH = Path(
    os.environ.get("GOOGLE_CREDENTIALS_PATH", BASE_DIR / "credentials" / "credentials.json")
)
GOOGLE_TOKEN_PATH = Path(
    os.environ.get("GOOGLE_TOKEN_PATH", BASE_DIR / "credentials" / "token.json")
)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b-instruct")

# Claude (Anthropic API) powers the main chat/tool-calling loop specifically — the strongest
# tool-calling reliability available, worth the small real cost. Ollama stays local/free for the
# narrower structured-output helpers (memo/inbox triage, calendar/task match) which already work
# well there.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
AGENT_MAX_TOOL_ITERATIONS = int(os.environ.get("AGENT_MAX_TOOL_ITERATIONS", "20"))
INBOX_SCAN_INTERVAL_MINUTES = int(os.environ.get("INBOX_SCAN_INTERVAL_MINUTES", "30"))

LOCAL_TZ = ZoneInfo(os.environ.get("LOCAL_TZ", "Asia/Tokyo"))


def ensure_dirs() -> None:
    for path in (DATA_DIR, MEMOS_WATCH_DIR, JOURNAL_DIR, GOOGLE_CREDENTIALS_PATH.parent, GOOGLE_TOKEN_PATH.parent):
        path.mkdir(parents=True, exist_ok=True)
