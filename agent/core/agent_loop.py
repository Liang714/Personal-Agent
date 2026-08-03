import re

from ollama._utils import convert_function_to_tool

from agent import config
from agent.errors import ChatModelUnavailableError
from agent.llm_client import anthropic_client, build_system_prompt
from agent.core.tools import TOOLS, TOOLS_BY_NAME

# Import capability modules so their @register_tool functions populate TOOLS.
from agent.capabilities import inbox, calendar, companion  # noqa: F401


def _to_anthropic_tool(func) -> dict:
    """Anthropic's tool schema is a flatter cousin of OpenAI's — reuse Ollama's own
    function-introspection (`convert_function_to_tool`) rather than writing a second schema
    generator, then reshape its OpenAI-style output into Anthropic's {name, description,
    input_schema} shape."""
    openai_shape = convert_function_to_tool(func).model_dump(exclude_none=True)["function"]
    return {
        "name": openai_shape["name"],
        "description": openai_shape["description"],
        "input_schema": openai_shape["parameters"],
    }


ANTHROPIC_TOOLS = [_to_anthropic_tool(f) for f in TOOLS]

MAX_TOKENS = 1024

WRAPUP_INSTRUCTION = (
    "You've hit the tool-call limit — do not call any more tools. Summarize what you found "
    "and any actions you already took (drafts created, events created, etc.) so far."
)

# Verbs used by the registered tools (add/delete/complete a calendar event, task, or email
# draft). A plain keyword check rather than another model call — false negatives just mean no
# retry (today's behavior); false positives cost one harmless extra round trip.
_ACTION_KEYWORDS = {
    "add", "create", "schedule", "book", "delete", "remove", "cancel",
    "complete", "finish", "mark", "draft", "reply",
}

RETRY_NUDGE = (
    "You did not call any tool in your last reply. If the user's message above asked you to "
    "perform an action (e.g. add, delete, or complete a calendar event, task, or email draft), "
    "you must call the matching tool now — do not just describe or claim the action in text. "
    "If nothing actually needs to be done, say so plainly instead of claiming an action was taken."
)

# Tools that create a new item — repeated calls to these in one request are capped at 1 unless
# the user's message names an explicit count. Structural guard, not a prompt request: verified
# live (with an earlier, weaker model) that a single ambiguous instruction ("at a random time")
# can make a model hedge by calling create_calendar_event twice with two different guesses in
# one turn, silently creating a duplicate event. Cheap insurance kept regardless of model.
_SINGLE_USE_TOOLS = {"create_calendar_event"}

_NUMBER_WORDS = {
    "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "both", "several", "multiple", "few", "couple",
}

HISTORY_BOUNDARY = (
    "Everything above this line is past conversation history, shown only for context (e.g. "
    "recalling names, preferences, or things already discussed). It is NOT a to-do list. Some of "
    "it may describe actions that were requested before — do not repeat, resume, retry, or "
    "double-check any of them. Only the user's latest message is live. If it doesn't itself ask "
    "for an action, do not call any tool, no matter what appears above."
)


def _looks_actionable(user_message: str) -> bool:
    words = set(re.findall(r"[a-z']+", user_message.lower()))
    return bool(words & _ACTION_KEYWORDS)


def _explicit_count_requested(user_message: str) -> bool:
    if re.search(r"\d", user_message):
        return True
    words = set(re.findall(r"[a-z']+", user_message.lower()))
    return bool(words & _NUMBER_WORDS)


def _call_model(messages: list, tools: list | None, system: str) -> object:
    try:
        return anthropic_client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            tools=tools or [],
        )
    except Exception as exc:  # noqa: BLE001
        raise ChatModelUnavailableError(
            f"Couldn't reach the Anthropic API ({config.ANTHROPIC_MODEL}): {exc}. Check that "
            "ANTHROPIC_API_KEY is set correctly in .env."
        ) from exc


def ask(user_message: str, history: list[dict] | None = None) -> str:
    system = build_system_prompt()
    if history:
        system = f"{system}\n\n{HISTORY_BOUNDARY}"

    messages = [*(history or []), {"role": "user", "content": user_message}]

    # Hard structural guard, not just a prompt request: history alone (even a single past "I'll
    # add X" reply) can make a capable tool-calling model re-execute an old, unrelated action on
    # a totally unrelated later message. If the CURRENT message doesn't itself look like an
    # action request, don't even offer tools on the first call — it becomes mechanically
    # impossible to act on stale context, rather than hoping the model chooses not to.
    actionable = _looks_actionable(user_message)
    allow_multiple = _explicit_count_requested(user_message)
    single_use_calls_made: set[str] = set()

    for i in range(config.AGENT_MAX_TOOL_ITERATIONS):
        tools = ANTHROPIC_TOOLS if (i > 0 or actionable) else None
        message = _call_model(messages, tools=tools, system=system)
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in message.content]})

        tool_uses = [b for b in message.content if b.type == "tool_use"]
        text = " ".join(b.text for b in message.content if b.type == "text").strip()

        if not tool_uses:
            if i == 0 and actionable:
                messages.append({"role": "user", "content": RETRY_NUDGE})
                continue
            return text

        tool_results = []
        for call in tool_uses:
            tool = TOOLS_BY_NAME.get(call.name)
            name = call.name
            if tool is None:
                result = f"Error: unknown tool '{name}'"
            elif name in _SINGLE_USE_TOOLS and not allow_multiple and name in single_use_calls_made:
                result = (
                    f"Skipped — only one {name} call is made per request unless you name an "
                    "exact number (e.g. 'add 2 events', 'both'). If you meant to create another "
                    "one, ask again with a number."
                )
            else:
                single_use_calls_made.add(name)
                try:
                    result = str(tool(**call.input))
                except Exception as exc:  # noqa: BLE001
                    result = f"Error calling {name}: {exc}"
            tool_results.append({"type": "tool_result", "tool_use_id": call.id, "content": result})
        messages.append({"role": "user", "content": tool_results})

    try:
        wrapup = _call_model(
            [*messages, {"role": "user", "content": WRAPUP_INSTRUCTION}], tools=None, system=system
        )
        text = " ".join(b.text for b in wrapup.content if b.type == "text").strip()
        return text or "Reached the tool-call limit; see actions taken above."
    except ChatModelUnavailableError:
        return (
            "Reached the tool-call limit before finishing, and couldn't reach the model to "
            "summarize. Any actions already taken (drafts, events) are not lost — check Gmail "
            "Drafts / Calendar directly."
        )
