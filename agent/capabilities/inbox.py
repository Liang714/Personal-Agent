import base64
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.text import MIMEText
from html import unescape

from googleapiclient.discovery import build
from pydantic import BaseModel

from agent import config
from agent.core.tools import register_tool
from agent.google_auth import get_credentials


@dataclass
class EmailMessage:
    id: str
    thread_id: str
    sender: str
    subject: str
    snippet: str
    body: str


class EmailProvider(ABC):
    @abstractmethod
    def list_unread(self, max_results: int = 20) -> list[EmailMessage]: ...

    @abstractmethod
    def get_message(self, message_id: str) -> EmailMessage: ...

    @abstractmethod
    def create_draft_reply(self, thread_id: str, to: str, subject: str, body: str) -> str: ...


def _strip_html(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _walk_body_parts(payload: dict) -> tuple[str | None, str | None]:
    """Return (plain_text, html_text), preferring the first part found of each type."""
    plain, html = None, None
    data = payload.get("body", {}).get("data")
    if data and payload.get("mimeType") == "text/plain":
        plain = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    elif data and payload.get("mimeType") == "text/html":
        html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        part_plain, part_html = _walk_body_parts(part)
        plain = plain or part_plain
        html = html or part_html
    return plain, html


def _extract_body(payload: dict) -> str:
    plain, html = _walk_body_parts(payload)
    if plain and plain.strip():
        return plain.strip()
    if html and html.strip():
        return _strip_html(html)
    return "[No readable text content found in this email]"


def _to_email_message(full: dict) -> EmailMessage:
    headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
    return EmailMessage(
        id=full["id"],
        thread_id=full["threadId"],
        sender=headers.get("From", ""),
        subject=headers.get("Subject", ""),
        snippet=full.get("snippet", ""),
        body=_extract_body(full["payload"]),
    )


class GmailProvider(EmailProvider):
    def __init__(self):
        self._service = build("gmail", "v1", credentials=get_credentials())

    def list_unread(self, max_results: int = 20) -> list[EmailMessage]:
        resp = (
            self._service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results)
            .execute()
        )
        messages = []
        for m in resp.get("messages", []):
            full = self._service.users().messages().get(userId="me", id=m["id"], format="full").execute()
            messages.append(_to_email_message(full))
        return messages

    def get_message(self, message_id: str) -> EmailMessage:
        full = self._service.users().messages().get(userId="me", id=message_id, format="full").execute()
        return _to_email_message(full)

    def create_draft_reply(self, thread_id: str, to: str, subject: str, body: str) -> str:
        msg = MIMEText(body)
        msg["To"] = to
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        draft = (
            self._service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}})
            .execute()
        )
        return draft["id"]


# TODO(week3): module-level singleton isn't thread-safe once served via FastAPI — revisit
# with a lock or per-request provider.
_provider: EmailProvider | None = None


def _get_provider() -> EmailProvider:
    global _provider
    if _provider is None:
        _provider = GmailProvider()
    return _provider


@register_tool
def scan_inbox() -> str:
    """List unread inbox emails (id, sender, subject, short snippet) so they can be triaged."""
    unread = _get_provider().list_unread()
    if not unread:
        return "No unread emails."
    return "\n".join(f"[{m.id}] from {m.sender}: {m.subject} — {m.snippet}" for m in unread)


@register_tool
def get_message(message_id: str) -> str:
    """Get the full sender, subject, and body text of one email by id, e.g. before drafting a reply."""
    m = _get_provider().get_message(message_id)
    return f"From: {m.sender}\nSubject: {m.subject}\n\n{m.body}"


@register_tool
def draft_reply(message_id: str, body: str) -> str:
    """Create a Gmail draft reply to the given message id. Never sends automatically — the draft
    always waits in Gmail Drafts for the user to review and send themselves."""
    m = _get_provider().get_message(message_id)
    draft_id = _get_provider().create_draft_reply(m.thread_id, m.sender, m.subject, body)
    return f"Draft created (id={draft_id}) in Gmail Drafts. Not sent — waiting for user review."


class _TriageItem(BaseModel):
    message_id: str
    needs_reply: bool
    reason: str


class _TriageResult(BaseModel):
    items: list[_TriageItem]


_TRIAGE_PROMPT = """Here is a list of unread emails (id, sender, subject, snippet). For each \
one, decide whether it clearly needs a reply from the user (not just informational/automated \
notifications), and give a one-sentence reason either way.

{listing}"""


def run_scan_and_draft(dry_run: bool = False) -> str:
    """Triage the unread inbox and draft replies for anything that needs one.

    Deliberately does NOT delegate this whole multi-step decision to a single autonomous
    tool-calling loop: a local 7B model reliably narrates "I drafted a reply" without actually
    calling draft_reply when asked to plan-and-execute across many emails at once (verified via
    live testing). Instead, triage uses one bounded structured-output call (same reliable
    pattern as memos.py), and drafting is a separate, narrow ask() call per flagged email —
    the pattern that was confirmed to reliably invoke the tool.

    dry_run=True skips the drafting step entirely, only returning the triage summary.
    """
    from agent.core.agent_loop import ask
    from agent.llm_client import client

    unread = _get_provider().list_unread()
    if not unread:
        return "No unread emails."

    listing = "\n".join(f"[{m.id}] from {m.sender}: {m.subject} — {m.snippet}" for m in unread)
    response = client.chat(
        model=config.OLLAMA_MODEL,
        messages=[{"role": "user", "content": _TRIAGE_PROMPT.format(listing=listing)}],
        format=_TriageResult.model_json_schema(),
    )
    triage = _TriageResult.model_validate_json(response.message.content)
    for item in triage.items:
        item.message_id = item.message_id.strip("[] ")

    lines = ["Triage:"]
    for item in triage.items:
        flag = "needs reply" if item.needs_reply else "no reply needed"
        lines.append(f"  [{item.message_id}] {flag} — {item.reason}")

    to_draft = [item for item in triage.items if item.needs_reply]
    if dry_run:
        if to_draft:
            lines.append(f"\nDry run: would draft replies for {len(to_draft)} email(s), none created.")
        return "\n".join(lines)

    if to_draft:
        lines.append("\nDrafting replies:")
        for item in to_draft:
            result = ask(
                f"Look up email {item.message_id} with get_message, then draft an appropriate "
                "reply with draft_reply."
            )
            lines.append(f"  [{item.message_id}] {result}")
    else:
        lines.append("\nNo emails needed a reply.")

    return "\n".join(lines)
