from pathlib import Path

from dotenv import load_dotenv
import os

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
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b-instruct")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")

DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMOS_WATCH_DIR.mkdir(parents=True, exist_ok=True)
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
