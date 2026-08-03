from unittest.mock import MagicMock, patch

import pytest

from agent.core.agent_loop import _call_model, ask
from agent.core.tools import TOOLS_BY_NAME
from agent.errors import ChatModelUnavailableError


def _text_block(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    block.model_dump.return_value = {"type": "text", "text": text}
    return block


def _tool_use_block(name: str, input: dict | None = None, call_id: str = "call_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.id = call_id
    block.name = name
    block.input = input or {}
    block.model_dump.return_value = {"type": "tool_use", "id": call_id, "name": name, "input": input or {}}
    return block


def _message(*blocks):
    """Build a fake Anthropic Message shaped like `response` (with `.content` blocks)."""
    msg = MagicMock()
    msg.content = list(blocks)
    return msg


@patch("agent.core.agent_loop.anthropic_client")
def test_call_model_wraps_connection_errors(mock_anthropic_client):
    mock_anthropic_client.messages.create.side_effect = ConnectionError("boom")

    with pytest.raises(ChatModelUnavailableError):
        _call_model([{"role": "user", "content": "hi"}], tools=[], system="sys")


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_retries_once_when_actionable_message_gets_no_tool_call(mock_anthropic_client):
    first = _message(_text_block("I've added the dentist appointment!"))
    second = _message(_text_block("Done — actually added it this time."))
    mock_anthropic_client.messages.create.side_effect = [first, second]

    result = ask("add dentist event today at 5pm")

    assert mock_anthropic_client.messages.create.call_count == 2
    assert result == "Done — actually added it this time."


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_does_not_retry_non_actionable_message(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = _message(_text_block("Hello! How can I help you today?"))

    result = ask("hello")

    assert mock_anthropic_client.messages.create.call_count == 1
    assert result == "Hello! How can I help you today?"


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_withholds_tools_for_non_actionable_message_even_with_actionable_history(mock_anthropic_client):
    """Regression guard for a real bug found live (with an earlier model backing chat): a single
    past assistant reply describing a calendar add ("I will add a dentist appointment...")
    sitting in history was enough to make the model re-execute it in response to an unrelated
    later message ("hello"), actually creating duplicate real calendar events. Withholding tools
    entirely on the first call for a non-actionable message makes this mechanically impossible,
    regardless of history content or which model is behind the chat."""
    mock_anthropic_client.messages.create.return_value = _message(_text_block("Hello!"))
    history = [
        {"role": "user", "content": "add dentist appointment at 8pm today and tomorrow"},
        {"role": "assistant", "content": "Sure, I will add a dentist appointment for both today and tomorrow."},
    ]

    ask("hello, are you working?", history=history)

    _, kwargs = mock_anthropic_client.messages.create.call_args_list[0]
    assert kwargs["tools"] == []


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_offers_tools_for_actionable_message(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = _message(_text_block("Added."))

    ask("add dentist event today at 5pm")

    _, kwargs = mock_anthropic_client.messages.create.call_args_list[0]
    assert kwargs["tools"]


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_retry_recovers_a_real_tool_call(mock_anthropic_client):
    fake_tool = MagicMock(return_value="fake tool result")

    no_tool_call = _message(_text_block("I've added the event!"))
    with_tool_call = _message(_tool_use_block("fake_tool"))
    wrapup = _message(_text_block("Added it — here's the fake tool result."))
    mock_anthropic_client.messages.create.side_effect = [no_tool_call, with_tool_call, wrapup]

    with patch.dict("agent.core.agent_loop.TOOLS_BY_NAME", {"fake_tool": fake_tool}):
        result = ask("add a random event tomorrow")

    assert mock_anthropic_client.messages.create.call_count == 3
    fake_tool.assert_called_once_with()
    assert result == "Added it — here's the fake tool result."


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_caps_duplicate_create_calendar_event_calls_without_explicit_count(mock_anthropic_client):
    """Regression guard: asked to add one event "at a random time", a model could hedge by
    calling create_calendar_event twice in one turn with two different guessed times, silently
    creating a duplicate event. Only the first call of a repeated single-use tool should execute
    unless the user's message names an explicit count."""
    fake_create = MagicMock(return_value="created")

    with_calls = _message(
        _tool_use_block("create_calendar_event", {"summary": "Dentist"}, call_id="a"),
        _tool_use_block("create_calendar_event", {"summary": "Dentist"}, call_id="b"),
    )
    wrapup = _message(_text_block("Added one event."))
    mock_anthropic_client.messages.create.side_effect = [with_calls, wrapup]

    with patch.dict("agent.core.agent_loop.TOOLS_BY_NAME", {"create_calendar_event": fake_create}):
        ask("add dentist event today at a random time")

    fake_create.assert_called_once()
    second_call_messages = mock_anthropic_client.messages.create.call_args_list[1].kwargs["messages"]
    tool_result_blocks = [b for m in second_call_messages if m.get("role") == "user" for b in m["content"]
                           if isinstance(b, dict) and b.get("type") == "tool_result"]
    assert any("Skipped" in b["content"] for b in tool_result_blocks)


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_allows_multiple_create_calendar_event_calls_with_explicit_count(mock_anthropic_client):
    fake_create = MagicMock(return_value="created")

    with_calls = _message(
        _tool_use_block("create_calendar_event", {"summary": "Dentist"}, call_id="a"),
        _tool_use_block("create_calendar_event", {"summary": "Dentist"}, call_id="b"),
    )
    wrapup = _message(_text_block("Added both events."))
    mock_anthropic_client.messages.create.side_effect = [with_calls, wrapup]

    with patch.dict("agent.core.agent_loop.TOOLS_BY_NAME", {"create_calendar_event": fake_create}):
        ask("add 2 dentist events today")

    assert fake_create.call_count == 2


@patch("agent.core.agent_loop.anthropic_client")
def test_ask_passes_tool_input_dict_directly(mock_anthropic_client):
    fake_tool = MagicMock(return_value="created")

    with_tool_call = _message(_tool_use_block("fake_tool", {"summary": "Lunch", "date": "2026-08-05"}))
    wrapup = _message(_text_block("Done."))
    mock_anthropic_client.messages.create.side_effect = [with_tool_call, wrapup]

    with patch.dict("agent.core.agent_loop.TOOLS_BY_NAME", {"fake_tool": fake_tool}):
        ask("add lunch on 2026-08-05")

    fake_tool.assert_called_once_with(summary="Lunch", date="2026-08-05")


def test_low_level_id_tools_not_registered():
    """The model must never be offered a tool that takes a raw id directly - it's unreliable
    at resolving natural language to the right id itself. Only the description-matching tools
    should be exposed; the low-level id-taking functions still exist but aren't @register_tool'd."""
    unregistered = {"complete_task", "delete_task", "delete_calendar_event"}
    registered = {"complete_tasks", "delete_tasks", "delete_calendar_events"}

    assert unregistered.isdisjoint(TOOLS_BY_NAME.keys())
    assert registered.issubset(TOOLS_BY_NAME.keys())
