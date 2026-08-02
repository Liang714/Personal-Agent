import { useState } from "react";
import { ApiError, inboxScan } from "../api";

export default function InboxPanel() {
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function runScan(dryRun: boolean) {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const { result } = await inboxScan(dryRun);
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
        <h2>Inbox</h2>
        <div className="panel-actions">
          <button onClick={() => runScan(true)} disabled={loading}>
            Preview (dry run)
          </button>
          <button onClick={() => runScan(false)} disabled={loading} className="primary">
            Scan &amp; draft replies
          </button>
        </div>
      </div>
      <p className="panel-note">Drafts are never sent automatically — they wait in Gmail Drafts for your review.</p>
      {loading && <p className="loading">Scanning inbox and consulting the agent — this can take a minute…</p>}
      {error && <p className="error-text">{error}</p>}
      {result && <pre className="result-block">{result}</pre>}
    </div>
  );
}
