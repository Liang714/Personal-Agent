from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta

from googleapiclient.discovery import build

from agent import config
from agent.core.tools import register_tool
from agent.google_auth import get_credentials


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


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self):
        self._service = build("calendar", "v3", credentials=get_credentials())

    def list_events(self, time_min: datetime, time_max: datetime) -> list[CalendarEvent]:
        resp = (
            self._service.events()
            .list(
                calendarId="primary",
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
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
        created = self._service.events().insert(calendarId="primary", body=event).execute()
        return created["id"]


# TODO(week3): module-level singleton isn't thread-safe once served via FastAPI — revisit
# with a lock or per-request provider.
_provider: CalendarProvider | None = None


def _get_provider() -> CalendarProvider:
    global _provider
    if _provider is None:
        _provider = GoogleCalendarProvider()
    return _provider


@register_tool
def list_today_events() -> str:
    """List today's calendar events with start/end times."""
    now_local = datetime.now(config.LOCAL_TZ)
    start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)
    events = _get_provider().list_events(start_of_day, end_of_day)
    if not events:
        return "No events today."
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
