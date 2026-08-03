import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from google.auth.exceptions import TransportError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ValidationError

from agent import config
from agent.core.tools import register_tool
from agent.errors import GoogleApiUnavailableError, MatchExtractionError
from agent.google_auth import get_credentials
from agent.llm_client import client


def _execute(request):
    """Run a Google API request with retries for transient errors, and turn any failure into a
    clear, user-facing error instead of a raw traceback (e.g. DNS/network blips talking to
    Google's servers)."""
    try:
        return request.execute(num_retries=3)
    except (TransportError, HttpError, OSError) as exc:
        raise GoogleApiUnavailableError(
            f"Couldn't reach Google Calendar — check your network and try again. ({exc})"
        ) from exc


@dataclass
class CalendarEvent:
    id: str
    summary: str
    start: str
    end: str


class CalendarProvider(ABC):
    @abstractmethod
    def list_events(self, time_min: datetime, time_max: datetime) -> list[CalendarEvent]: ...

    @abstractmethod
    def create_event(self, summary: str, start: datetime, end: datetime, description: str = "") -> str: ...

    @abstractmethod
    def delete_event(self, event_id: str) -> None: ...


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self):
        self._service = build("calendar", "v3", credentials=get_credentials())

    def list_events(self, time_min: datetime, time_max: datetime) -> list[CalendarEvent]:
        resp = _execute(
            self._service.events().list(
                calendarId="primary",
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
        )
        events = []
        for e in resp.get("items", []):
            start = e["start"].get("dateTime", e["start"].get("date"))
            end = e["end"].get("dateTime", e["end"].get("date"))
            events.append(CalendarEvent(id=e["id"], summary=e.get("summary", "(no title)"), start=start, end=end))
        return events

    def create_event(self, summary: str, start: datetime, end: datetime, description: str = "") -> str:
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": str(config.LOCAL_TZ)},
            "end": {"dateTime": end.isoformat(), "timeZone": str(config.LOCAL_TZ)},
        }
        created = _execute(self._service.events().insert(calendarId="primary", body=event))
        return created["id"]

    def delete_event(self, event_id: str) -> None:
        _execute(self._service.events().delete(calendarId="primary", eventId=event_id))


# FastAPI runs sync route handlers in a thread pool, so concurrent requests can genuinely race
# on first construction — double-checked locking avoids building (and discarding) more than one.
_provider: CalendarProvider | None = None
_provider_lock = threading.Lock()


def _get_provider() -> CalendarProvider:
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = GoogleCalendarProvider()
    return _provider


def _day_range(d: date) -> tuple[datetime, datetime]:
    start_of_day = datetime.combine(d, time.min, tzinfo=config.LOCAL_TZ)
    return start_of_day, start_of_day + timedelta(days=1)


def _resolve_date(date_str: str) -> date:
    return date.fromisoformat(date_str) if date_str else datetime.now(config.LOCAL_TZ).date()


@register_tool
def list_events_on_date(date: str = "") -> str:
    """List calendar events with start/end times for a given date ('YYYY-MM-DD'), or today if
    date is omitted."""
    d = _resolve_date(date)
    events = _get_provider().list_events(*_day_range(d))
    if not events:
        return f"No events on {d.isoformat()}."
    return "\n".join(f"[{e.id}] {e.start} - {e.end}: {e.summary}" for e in events)


@register_tool
def create_calendar_event(summary: str, date: str, start_time: str, end_time: str, description: str = "") -> str:
    """Create a calendar event. date is 'YYYY-MM-DD', start_time and end_time are 'HH:MM' in
    24-hour format — all plain wall-clock values in the user's own local timezone. Do not
    include any UTC offset, timezone letter, or timezone conversion; local time is always
    assumed automatically."""
    start = datetime.fromisoformat(f"{date}T{start_time}").replace(tzinfo=config.LOCAL_TZ)
    end = datetime.fromisoformat(f"{date}T{end_time}").replace(tzinfo=config.LOCAL_TZ)
    event_id = _get_provider().create_event(summary, start, end, description)
    return f"Event created (id={event_id})."


def delete_calendar_event(event_id: str) -> str:
    """Cancel/remove a calendar event by id."""
    _get_provider().delete_event(event_id)
    return f"Event {event_id} deleted."


class _MatchedEventIds(BaseModel):
    event_ids: list[str]
    explanation: str


_EVENT_MATCH_PROMPT = """Here is the real list of calendar events on {date} (id, start, end, summary). \
A user asked to delete event(s) matching this description: "{description}"

Events on {date}:
{listing}

Return the id(s) of the event(s) that match the description. If it clearly refers to one event, \
return just that one id. If it refers to multiple events (e.g. "both", "all of them"), return \
all matching ids. If you are not confident any event matches, return an empty list — never guess \
or invent an id that isn't in the list above."""


def _match_event_ids(description: str, events: list[CalendarEvent], d: date) -> list[str]:
    listing = "\n".join(f"[{e.id}] {e.start} - {e.end}: {e.summary}" for e in events)
    response = client.chat(
        model=config.OLLAMA_MODEL,
        messages=[
            {
                "role": "user",
                "content": _EVENT_MATCH_PROMPT.format(description=description, listing=listing, date=d.isoformat()),
            }
        ],
        format=_MatchedEventIds.model_json_schema(),
    )
    content = response.message.content
    if not content:
        raise MatchExtractionError("The model returned no content while matching the event description.")
    try:
        matched = _MatchedEventIds.model_validate_json(content)
    except ValidationError as exc:
        raise MatchExtractionError(f"Couldn't parse the model's match output: {exc}") from exc

    real_ids = {e.id for e in events}
    cleaned = [eid.strip("[] ") for eid in matched.event_ids]
    return [eid for eid in cleaned if eid in real_ids]


@register_tool
def delete_calendar_events(description: str, date: str = "") -> str:
    """Delete one or more calendar events matching a natural-language description (e.g. "the
    dentist appointment", "both meetings this afternoon", "the 3pm one"). Do not invent or guess
    an event id yourself — pass the user's own description and this tool will look up the real
    events on the given date and match against them itself. date is 'YYYY-MM-DD', or omit it for
    today. If nothing matches confidently, nothing is deleted."""
    d = _resolve_date(date)
    events = _get_provider().list_events(*_day_range(d))
    if not events:
        return f"No events on {d.isoformat()} to delete."

    matched_ids = _match_event_ids(description, events, d)
    if not matched_ids:
        listing = "\n".join(f"[{e.id}] {e.start} - {e.end}: {e.summary}" for e in events)
        return (
            f'Couldn\'t confidently match "{description}" to any event on {d.isoformat()} — '
            f"nothing was deleted. Events on {d.isoformat()}:\n{listing}"
        )

    deleted = [e for e in events if e.id in matched_ids]
    for e in deleted:
        delete_calendar_event(e.id)

    lines = [f"Deleted {len(deleted)} event(s):"]
    lines += [f"  - {e.summary} ({e.start} - {e.end})" for e in deleted]
    return "\n".join(lines)
