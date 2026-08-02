from datetime import datetime
from unittest.mock import MagicMock, patch

from agent import config
from agent.capabilities.calendar import GoogleCalendarProvider, create_calendar_event, delete_calendar_event


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
