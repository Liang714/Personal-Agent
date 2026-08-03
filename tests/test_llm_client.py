from agent.llm_client import build_system_prompt


def test_system_prompt_scopes_actions_to_latest_message():
    """Regression guard for a real bug: with full conversation history fed back on every turn,
    a capable tool-calling model re-executed an old, unrelated "add an event" request from
    history in response to a plain "hello" — actually creating duplicate real calendar events.
    The prompt must explicitly scope tool use to the user's latest message only."""
    prompt = build_system_prompt().lower()
    assert "most recent message" in prompt
    assert "history" in prompt
