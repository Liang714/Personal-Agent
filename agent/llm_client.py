from datetime import datetime

from anthropic import Anthropic
from ollama import Client

from agent import config

client = Client(host=config.OLLAMA_HOST)

# Powers agent_loop.py's chat/tool-calling loop specifically. The rest of this project's LLM
# calls (memo/inbox triage, calendar/task match) stay on the local `client` above.
anthropic_client = Anthropic(api_key=config.ANTHROPIC_API_KEY)


def build_system_prompt() -> str:
    now = datetime.now(config.LOCAL_TZ)
    return (
        "You are a personal daily-task agent for a single user. "
        f"The current date and time is {now.strftime('%A, %Y-%m-%d %H:%M')} ({config.LOCAL_TZ}) — "
        "use this to resolve relative dates like 'today', 'tomorrow', or 'next week'; never guess "
        "or assume a different date. "
        "You have tools to read/manage their inbox and calendar, process voice memos into tasks and "
        "journal entries, and answer general questions using whatever context is relevant. Never send "
        "an email yourself — email replies are always created as drafts for the user to review and "
        "send. When a tool exists for an action (e.g. draft_reply, create_calendar_event), you must "
        "actually call it — never just describe what you would do without calling it. "
        "Only act on the user's most recent message. Earlier turns in this conversation are past "
        "history for context only — never re-run, resume, or repeat an action from an earlier turn "
        "just because it appears in the history. If the latest message doesn't itself ask for an "
        "action, don't call any tool, even if a previous message did. "
        "Be concise and direct."
    )
