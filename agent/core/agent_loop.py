from agent import config
from agent.llm_client import client, SYSTEM_PROMPT
from agent.core.tools import TOOLS, TOOLS_BY_NAME

# Import capability modules so their @register_tool functions populate TOOLS.
from agent.capabilities import inbox, calendar, companion  # noqa: F401

MAX_TOOL_ITERATIONS = 8


def ask(user_message: str, history: list[dict] | None = None) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *(history or []),
        {"role": "user", "content": user_message},
    ]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.chat(model=config.OLLAMA_MODEL, messages=messages, tools=TOOLS)
        messages.append(response.message)

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

    return "Reached max tool-call iterations without a final answer."
