from unittest.mock import patch

import pytest

from agent.core.agent_loop import _call_model
from agent.errors import OllamaUnavailableError


@patch("agent.core.agent_loop.client")
def test_call_model_wraps_connection_errors(mock_client):
    mock_client.chat.side_effect = ConnectionError("boom")

    with pytest.raises(OllamaUnavailableError):
        _call_model([{"role": "user", "content": "hi"}], tools=[])
