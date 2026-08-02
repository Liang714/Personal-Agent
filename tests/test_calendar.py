from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agent import config
from agent.capabilities.calendar import (
    CalendarEvent,
    GoogleCalendarProvider,
    create_calendar_event,
    delete_calendar_event,
    delete_calendar_events,
)
from agent.errors import MatchExtractionError


@patch("agent.capabilities.calendar._get_provider")
def test_create_calendar_event_assumes_local_tz(mock_get_provider):
    mock_provider = MagicMock()
    mock_provider.create_event.return_value = "evt123"
    mock_get_provider.return_value = mock_provider

    result = create_calendar_event("Test event", "2026-08-03", "15:00", "15:30")

    assert "evt123" in result
    args, _ = mock_provider.create_event.call_args
    _, start, end, _ = args
    assert start.tzinfo == config.LOCAL_TZ
    assert (start.hour, start.minute) == (15, 0)
    assert (end.hour, end.minute) == (15, 30)


@patch("agent.capabilities.calendar.get_credentials")
@patch("agent.capabilities.calendar.build")
def test_provider_create_event_sets_timezone(mock_build, mock_get_creds):
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.events.return_value.insert.return_value.execute.return_value = {"id": "abc"}

    provider = GoogleCalendarProvider()
    start = datetime(2026, 8, 3, 15, 0, tzinfo=config.LOCAL_TZ)
    end = datetime(2026, 8, 3, 15, 30, tzinfo=config.LOCAL_TZ)
    event_id = provider.create_event("Test", start, end)

    assert event_id == "abc"
    _, kwargs = mock_service.events.return_value.insert.call_args
    body = kwargs["body"]
    assert body["start"]["timeZone"] == str(config.LOCAL_TZ)
    assert body["end"]["timeZone"] == str(config.LOCAL_TZ)


@patch("agent.capabilities.calendar._get_provider")
def test_delete_calendar_event_calls_provider(mock_get_provider):
    mock_provider = MagicMock()
    mock_get_provider.return_value = mock_provider

    result = delete_calendar_event("evt123")

    mock_provider.delete_event.assert_called_once_with("evt123")
    assert "evt123" in result


@patch("agent.capabilities.calendar.get_credentials")
@patch("agent.capabilities.calendar.build")
def test_provider_delete_event_calls_google_api(mock_build, mock_get_creds):
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    provider = GoogleCalendarProvider()
    provider.delete_event("evt123")

    mock_service.events.return_value.delete.assert_called_once_with(calendarId="primary", eventId="evt123")


def _two_events():
    return [
        CalendarEvent(id="evt1", summary="Dentist appointment", start="10:00", end="10:30"),
        CalendarEvent(id="evt2", summary="Team standup", start="11:00", end="11:15"),
    ]


def _mock_chat_response(mock_client, content: str):
    mock_response = MagicMock()
    mock_response.message.content = content
    mock_client.chat.return_value = mock_response


@patch("agent.capabilities.calendar.client")
@patch("agent.capabilities.calendar._get_provider")
def test_delete_calendar_events_no_events_today(mock_get_provider, mock_client):
    mock_provider = MagicMock()
    mock_provider.list_events.return_value = []
    mock_get_provider.return_value = mock_provider

    result = delete_calendar_events("the dentist appointment")

    mock_client.chat.assert_not_called()
    assert result == "No events today to delete."


@patch("agent.capabilities.calendar.client")
@patch("agent.capabilities.calendar._get_provider")
def test_delete_calendar_events_single_match(mock_get_provider, mock_client):
    mock_provider = MagicMock()
    mock_provider.list_events.return_value = _two_events()
    mock_get_provider.return_value = mock_provider
    _mock_chat_response(mock_client, '{"event_ids": ["evt1"], "explanation": "matches dentist"}')

    result = delete_calendar_events("the dentist appointment")

    mock_provider.delete_event.assert_called_once_with("evt1")
    assert "Dentist appointment" in result
    assert "Team standup" not in result


@patch("agent.capabilities.calendar.client")
@patch("agent.capabilities.calendar._get_provider")
def test_delete_calendar_events_multiple_match(mock_get_provider, mock_client):
    mock_provider = MagicMock()
    mock_provider.list_events.return_value = _two_events()
    mock_get_provider.return_value = mock_provider
    _mock_chat_response(mock_client, '{"event_ids": ["evt1", "evt2"], "explanation": "both"}')

    result = delete_calendar_events("both events")

    assert mock_provider.delete_event.call_count == 2
    mock_provider.delete_event.assert_any_call("evt1")
    mock_provider.delete_event.assert_any_call("evt2")
    assert "Dentist appointment" in result
    assert "Team standup" in result


@patch("agent.capabilities.calendar.client")
@patch("agent.capabilities.calendar._get_provider")
def test_delete_calendar_events_no_confident_match(mock_get_provider, mock_client):
    mock_provider = MagicMock()
    mock_provider.list_events.return_value = _two_events()
    mock_get_provider.return_value = mock_provider
    _mock_chat_response(mock_client, '{"event_ids": [], "explanation": "nothing matches"}')

    result = delete_calendar_events("the haircut appointment")

    mock_provider.delete_event.assert_not_called()
    assert "haircut appointment" in result
    assert "Dentist appointment" in result  # today's real events listed back


@patch("agent.capabilities.calendar.client")
@patch("agent.capabilities.calendar._get_provider")
def test_delete_calendar_events_rejects_hallucinated_id(mock_get_provider, mock_client):
    mock_provider = MagicMock()
    mock_provider.list_events.return_value = _two_events()
    mock_get_provider.return_value = mock_provider
    _mock_chat_response(
        mock_client, '{"event_ids": ["evt1", "evt_made_up"], "explanation": "one real, one not"}'
    )

    result = delete_calendar_events("the dentist appointment")

    mock_provider.delete_event.assert_called_once_with("evt1")
    assert "Dentist appointment" in result


@patch("agent.capabilities.calendar.client")
@patch("agent.capabilities.calendar._get_provider")
def test_delete_calendar_events_raises_on_invalid_json(mock_get_provider, mock_client):
    mock_provider = MagicMock()
    mock_provider.list_events.return_value = _two_events()
    mock_get_provider.return_value = mock_provider
    _mock_chat_response(mock_client, "not json")

    with pytest.raises(MatchExtractionError):
        delete_calendar_events("the dentist appointment")
