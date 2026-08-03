# personal-agent

A personal multimodal AI agent: inbox/calendar management, a general companion, and a voice-memo-to-task/journal converter. Backend + CLI + API + a web UI (see [web/](web/) — works on phone browsers too, no native app needed).

**Hybrid local/cloud LLM setup**: the main chat/tool-calling loop (`agent/core/agent_loop.py`) runs on the **Anthropic API** (Claude Haiku by default) — tool-calling reliability there matters enough to be worth a small real cost (needs billing set up at console.anthropic.com). Everything else — memo/inbox triage, calendar/task description-matching — runs on local [Ollama](https://ollama.com) (`qwen2.5:14b-instruct`), which stays free and already works well for those narrower, single-purpose calls. Speech-to-text is local `faster-whisper`.

## Setup

1. Make sure Ollama is installed and running:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"   # if installed without Homebrew, as done here
   export OLLAMA_MODELS="$HOME/.local/ollama/models"
   ollama serve &
   ollama pull qwen2.5:14b-instruct
   ```
2. Set up the Python environment:
   ```bash
   conda activate personal-agent
   pip install -e .          # add ".[dev]" instead to also get pytest
   cp .env.example .env
   ```
   Then add an Anthropic API key to `.env` (`ANTHROPIC_API_KEY=`) — get one from console.anthropic.com (requires billing set up). Without it, chat will return a clear "couldn't reach the Anthropic API" error; every other feature (memo, inbox, calendar API endpoints) still works.
3. For Gmail/Calendar: run `python -m agent.cli auth setup` once (opens a browser for Google consent). See the plan file for the one-time Google Cloud Console setup this depends on.

## Usage

```bash
python -m agent.cli chat "what's on my plate today?"     # one-shot
python -m agent.cli chat                                  # interactive REPL, remembers context via SQLite
python -m agent.cli memo path/to/file.m4a
python -m agent.cli inbox scan                             # triage + draft replies (never auto-sends)
python -m agent.cli inbox scan --dry-run                   # triage only, no drafts created
python -m agent.cli inbox daemon --interval 30              # repeat inbox scan every N minutes until Ctrl+C
python -m agent.cli calendar today
python -m agent.cli serve                                   # minimal HTTP API on :8000 (/chat, /memo, /inbox/scan, /calendar/today)
```

Drop audio files into `data/memos/` (or point `MEMOS_WATCH_DIR` at a folder synced from your phone) and run `memo` against them.

Logs go to `data/agent.log` as well as stdout.

## Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/
```

## Web UI

See [web/README.md](web/README.md). In short: start `python -m agent.cli serve`, then `cd web && npm run dev`.

See `/Users/liang/.claude/plans/i-am-going-to-cheeky-ember.md` for the full build plan.
