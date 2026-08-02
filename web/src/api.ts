const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(`Couldn't reach the backend at ${BASE_URL}. Is \`python -m agent.cli serve\` running?`);
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.error) message = body.error;
    } catch {
      // ignore, use default message
    }
    throw new ApiError(message);
  }

  return res.json() as Promise<T>;
}

export function chat(message: string): Promise<{ response: string }> {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export function inboxScan(dryRun: boolean): Promise<{ result: string }> {
  return request(`/inbox/scan?dry_run=${dryRun}`);
}

export function calendarToday(): Promise<{ result: string }> {
  return request("/calendar/today");
}

export interface MemoResult {
  transcript: string;
  tasks: string[];
  task_ids: number[];
  journal_entry: string;
  journal_path: string | null;
}

export function uploadMemo(file: File): Promise<MemoResult> {
  const formData = new FormData();
  formData.append("file", file);
  return request("/memo", { method: "POST", body: formData });
}
