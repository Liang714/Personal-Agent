import { useEffect, useState } from "react";
import {
  ApiError,
  createCalendarEvent,
  deleteCalendarEvent,
  listCalendarEvents,
  type CalendarEvent,
} from "../api";

function todayDateInput(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function formatEventTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function CalendarPanel() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [summary, setSummary] = useState("");
  const [date, setDate] = useState(todayDateInput());
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const items = await listCalendarEvents();
      items.sort((a, b) => a.start.localeCompare(b.start));
      setEvents(items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onDelete(eventId: string) {
    setDeletingId(eventId);
    setError(null);
    try {
      await deleteCalendarEvent(eventId);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setDeletingId(null);
    }
  }

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!summary.trim() || !date || !startTime || !endTime) return;

    setCreating(true);
    setFormError(null);
    try {
      await createCalendarEvent({ summary: summary.trim(), date, start_time: startTime, end_time: endTime });
      setSummary("");
      setStartTime("");
      setEndTime("");
      setShowForm(false);
      await refresh();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Calendar — today</h2>
        <div className="panel-actions">
          <button onClick={refresh} disabled={loading}>
            Refresh
          </button>
          <button onClick={() => setShowForm((s) => !s)} className="primary">
            {showForm ? "Cancel" : "Add event"}
          </button>
        </div>
      </div>
      <p className="panel-note">
        Reads and writes your calendar directly — no AI involved in adding or removing events, so
        it always works.
      </p>

      {showForm && (
        <form onSubmit={onCreate} className="event-form">
          <input
            type="text"
            placeholder="Event title"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            required
          />
          <div className="event-form-row">
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
            <input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} required />
            <span className="event-form-sep">to</span>
            <input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} required />
          </div>
          {formError && <p className="error-text">{formError}</p>}
          <button type="submit" disabled={creating} className="primary">
            {creating ? "Adding…" : "Add"}
          </button>
        </form>
      )}

      {loading && <p className="loading">Loading today's events…</p>}
      {error && <p className="error-text">{error}</p>}

      {!loading && events.length === 0 && <p className="empty-hint">No events today.</p>}

      {events.length > 0 && (
        <ul className="event-list">
          {events.map((e) => (
            <li key={e.id} className="event-list-item">
              <div>
                <span className="event-list-time">
                  {formatEventTime(e.start)}–{formatEventTime(e.end)}
                </span>
                <span className="event-list-summary">{e.summary}</span>
              </div>
              <button onClick={() => onDelete(e.id)} disabled={deletingId === e.id} className="event-list-delete">
                {deletingId === e.id ? "Deleting…" : "Delete"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
