import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent import config
from agent.errors import AgentError, NotAuthenticatedError, OllamaUnavailableError, ReauthRequiredError
from agent.logging_config import setup_logging
from agent.storage.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.ensure_dirs()
    setup_logging()
    init_db()
    yield


app = FastAPI(title="personal-agent", lifespan=lifespan)

# Local-only personal app (API binds to 127.0.0.1), so a permissive localhost
# CORS policy for the web frontend's dev/preview servers is not a real exposure.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AgentError)
def handle_agent_error(_request, exc: AgentError):
    status = 500
    if isinstance(exc, OllamaUnavailableError):
        status = 503
    elif isinstance(exc, (NotAuthenticatedError, ReauthRequiredError)):
        status = 401
    return JSONResponse(status_code=status, content={"error": str(exc)})


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    from agent.capabilities.companion import load_recent_history, save_turn
    from agent.core.agent_loop import ask

    history = load_recent_history()
    response = ask(req.message, history=history)
    save_turn("user", req.message)
    save_turn("assistant", response)
    return ChatResponse(response=response)


@app.post("/memo")
async def memo(file: UploadFile = File(...)) -> dict:
    from agent.capabilities.memos import handle_memo_file

    suffix = Path(file.filename).suffix or ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    try:
        return handle_memo_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/inbox/scan")
def inbox_scan(dry_run: bool = False) -> dict:
    from agent.capabilities.inbox import run_scan_and_draft

    return {"result": run_scan_and_draft(dry_run=dry_run)}


@app.get("/calendar/today")
def calendar_today() -> dict:
    from agent.core.agent_loop import ask

    result = ask("What's on my calendar today? Use list_today_events. Flag any conflicts or back-to-back meetings.")
    return {"result": result}
