import base64
from unittest.mock import MagicMock, patch

import pytest

from agent.capabilities.inbox import GmailProvider, _extract_body, _strip_html
from agent.errors import GoogleApiUnavailableError


def test_strip_html_basic():
    html = "<p>Hello <b>world</b></p><br>Bye"
    text = _strip_html(html)
    assert "Hello" in text
    assert "world" in text
    assert "<" not in text


def test_strip_html_removes_script_and_style():
    html = "<style>.x{color:red}</style><script>alert(1)</script><p>Visible</p>"
    text = _strip_html(html)
    assert "Visible" in text
    assert "alert" not in text
    assert "color:red" not in text


def test_extract_body_prefers_plain_text():
    plain = base64.urlsafe_b64encode(b"plain text body").decode()
    html = base64.urlsafe_b64encode(b"<p>html body</p>").decode()
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": plain}},
            {"mimeType": "text/html", "body": {"data": html}},
        ],
    }
    assert _extract_body(payload) == "plain text body"


def test_extract_body_falls_back_to_html():
    html = base64.urlsafe_b64encode(b"<p>Only HTML here</p>").decode()
    payload = {"mimeType": "text/html", "body": {"data": html}}
    assert "Only HTML here" in _extract_body(payload)


def test_extract_body_no_content_sentinel():
    payload = {"mimeType": "multipart/mixed", "parts": []}
    assert _extract_body(payload) == "[No readable text content found in this email]"


@patch("agent.capabilities.inbox.get_credentials")
@patch("agent.capabilities.inbox.build")
def test_create_draft_reply_never_sends(mock_build, mock_get_creds):
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    provider = GmailProvider()
    provider.create_draft_reply("thread123", "someone@example.com", "Hello", "body text")

    mock_service.users.return_value.drafts.return_value.create.assert_called_once()
    mock_service.users.return_value.messages.return_value.send.assert_not_called()
    mock_service.users.return_value.drafts.return_value.send.assert_not_called()
    mock_service.users.return_value.drafts.return_value.create.return_value.execute.assert_called_once_with(
        num_retries=3
    )


@patch("agent.capabilities.inbox.get_credentials")
@patch("agent.capabilities.inbox.build")
def test_get_message_wraps_transient_network_error(mock_build, mock_get_creds):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.users.return_value.messages.return_value.get.return_value.execute.side_effect = OSError(
        "[Errno 8] nodename nor servname provided, or not known"
    )

    provider = GmailProvider()
    with pytest.raises(GoogleApiUnavailableError):
        provider.get_message("msg123")
