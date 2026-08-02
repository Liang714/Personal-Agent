from agent import config
from agent.errors import OllamaUnavailableError
from agent.llm_client import client, SYSTEM_PROMPT
from agent.core.tools import TOOLS, TOOLS_BY_NAME

# Import capability modules so their @register_tool functions populate TOOLS.
from agent.capabilities import inbox, calendar, companion  # noqa: F401

WRAPUP_INSTRUCTION = (
    "You've hit the tool-call limit — do not call any more tools. Summarize what you found "
    "and any actions you already took (drafts created, events created, etc.) so far."
)


def _call_model(messages: list, tools: list = TOOLS) -> object:
    try:
        return client.chat(model=config.OLLAMA_MODEL, messages=messages, tools=tools)
    except Exception as exc:  # noqa: BLE001
        raise OllamaUnavailableError(
            f"Couldn't reach Ollama at {config.OLLAMA_HOST}: {exc}. Is `ollama serve` running?"
        ) from exc


def ask(user_message: str, history: list[dict] | None = None) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *(history or []),
        {"role": "user", "content": user_message},
    ]

    for _ in range(config.AGENT_MAX_TOOL_ITERATIONS):
        response = _call_model(messages)
        messages.append(response.message.model_dump(exclude_none=True))

        if not response.message.tool_calls:
            return (response.message.content or "").strip()

        for call in response.message.tool_calls:
            tool = TOOLS_BY_NAME.get(call.function.name)
            if tool is None:
                result = f"Error: unknown tool '{call.function.name}'"
            else:
                try:
                    result = str(tool(**call.function.arguments))
                except Exception as exc:  # noqa: BLE001
                    result = f"Error calling {call.function.name}: {exc}"
            messages.append({"role": "tool", "tool_name": call.function.name, "content": result})

    try:
        wrapup = _call_model([*messages, {"role": "user", "content": WRAPUP_INSTRUCTION}], tools=[])
        return (wrapup.message.content or "").strip() or "Reached the tool-call limit; see actions taken above."
    except OllamaUnavailableError:
        return (
            "Reached the tool-call limit before finishing, and couldn't reach the model to "
            "summarize. Any actions already taken (drafts, events) are not lost — check Gmail "
            "Drafts / Calendar directly."
        )
