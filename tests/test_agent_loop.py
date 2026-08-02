from unittest.mock import patch

import pytest

from agent.core.agent_loop import _call_model
from agent.core.tools import TOOLS_BY_NAME
from agent.errors import OllamaUnavailableError


@patch("agent.core.agent_loop.client")
def test_call_model_wraps_connection_errors(mock_client):
    mock_client.chat.side_effect = ConnectionError("boom")

    with pytest.raises(OllamaUnavailableError):
        _call_model([{"role": "user", "content": "hi"}], tools=[])


def test_low_level_id_tools_not_registered():
    """The model must never be offered a tool that takes a raw id directly - it's unreliable
    at resolving natural language to the right id itself. Only the description-matching tools
    should be exposed; the low-level id-taking functions still exist but aren't @register_tool'd."""
    unregistered = {"complete_task", "delete_task", "delete_calendar_event"}
    registered = {"complete_tasks", "delete_tasks", "delete_calendar_events"}

    assert unregistered.isdisjoint(TOOLS_BY_NAME.keys())
    assert registered.issubset(TOOLS_BY_NAME.keys())
