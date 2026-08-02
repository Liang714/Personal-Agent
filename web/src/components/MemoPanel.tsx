import { useRef, useState } from "react";
import { ApiError, uploadMemo, type MemoResult } from "../api";

export default function MemoPanel() {
  const [result, setResult] = useState<MemoResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function onFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const memoResult = await uploadMemo(file);
      setResult(memoResult);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Voice memo</h2>
        <div className="panel-actions">
          <button onClick={() => fileInputRef.current?.click()} disabled={loading} className="primary">
            Upload a memo
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={onFileChosen}
            style={{ display: "none" }}
          />
        </div>
      </div>
      <p className="panel-note">Upload a voice recording — it's transcribed and split into tasks and a journal entry.</p>
      {loading && <p className="loading">Transcribing and processing…</p>}
      {error && <p className="error-text">{error}</p>}
      {result && (
        <div className="memo-result">
          <h3>Transcript</h3>
          <p>{result.transcript}</p>

          <h3>Tasks</h3>
          {result.tasks.length > 0 ? (
            <ul>
              {result.tasks.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          ) : (
            <p className="empty-hint">No tasks extracted.</p>
          )}

          <h3>Journal entry</h3>
          {result.journal_entry ? <p>{result.journal_entry}</p> : <p className="empty-hint">None.</p>}
        </div>
      )}
    </div>
  );
}
