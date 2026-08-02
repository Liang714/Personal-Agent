import { useState } from "react";
import { ApiError, calendarToday } from "../api";

export default function CalendarPanel() {
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { result } = await calendarToday();
      setResult(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Calendar</h2>
        <div className="panel-actions">
          <button onClick={load} disabled={loading} className="primary">
            What's on today?
          </button>
        </div>
      </div>
      {loading && <p className="loading">Checking your calendar…</p>}
      {error && <p className="error-text">{error}</p>}
      {result && <pre className="result-block">{result}</pre>}
    </div>
  );
}
