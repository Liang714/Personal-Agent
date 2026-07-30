# personal-agent

A personal multimodal AI agent: inbox/calendar management, a general companion, and a voice-memo-to-task/journal converter. Backend-only for now (CLI first, minimal API in Week 3+) — no phone/web UI yet.

Runs entirely locally and for free — no paid API keys required. LLM reasoning is via [Ollama](https://ollama.com) running `qwen2.5:7b-instruct`; speech-to-text is via local `faster-whisper`.

## Setup

1. Make sure Ollama is installed and running:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"   # if installed without Homebrew, as done here
   export OLLAMA_MODELS="$HOME/.local/ollama/models"
   ollama serve &
   ollama pull qwen2.5:7b-instruct
   ```
2. Set up the Python environment:
   ```bash
   conda activate personal-agent
   pip install -e .
   cp .env.example .env   # defaults work out of the box, no keys needed
   ```

## Usage

```bash
python -m agent.cli chat "what's on my plate today?"
python -m agent.cli memo path/to/file.m4a
```

Drop audio files into `data/memos/` (or point `MEMOS_WATCH_DIR` at a folder synced from your phone) and run `memo` against them.

Note: until Week 2/3 (inbox, calendar, companion) are built, `chat` has no real tools to call and will answer from the model's general knowledge only — it doesn't yet know anything about your actual email, calendar, or tasks.

See `/Users/liang/.claude/plans/i-am-going-to-cheeky-ember.md` for the full build plan.
