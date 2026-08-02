from unittest.mock import MagicMock, patch

import pytest

from agent.capabilities.memos import process_memo
from agent.errors import MemoExtractionError


@patch("agent.capabilities.memos.client")
def test_process_memo_raises_on_none_content(mock_client):
    mock_response = MagicMock()
    mock_response.message.content = None
    mock_client.chat.return_value = mock_response

    with pytest.raises(MemoExtractionError):
        process_memo("some transcript")


@patch("agent.capabilities.memos.client")
def test_process_memo_raises_on_invalid_json(mock_client):
    mock_response = MagicMock()
    mock_response.message.content = "not valid json {{{"
    mock_client.chat.return_value = mock_response

    with pytest.raises(MemoExtractionError):
        process_memo("some transcript")


@patch("agent.capabilities.memos.client")
def test_process_memo_success(mock_client):
    mock_response = MagicMock()
    mock_response.message.content = '{"tasks": ["do a thing"], "journal_entry": "felt good"}'
    mock_client.chat.return_value = mock_response

    result = process_memo("some transcript")
    assert result.tasks == ["do a thing"]
    assert result.journal_entry == "felt good"
