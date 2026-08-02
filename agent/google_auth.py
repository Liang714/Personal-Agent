from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from agent import config
from agent.errors import AgentError, NotAuthenticatedError, ReauthRequiredError

# gmail.compose grants both draft-creation AND send permission — Google has no draft-only
# scope. The "never auto-send" guarantee in agent/capabilities/inbox.py is enforced purely
# by code convention (only ever calling drafts().create(), never .send()), not by this scope.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar",
]


def run_setup_flow() -> None:
    if not config.GOOGLE_CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Missing OAuth client credentials at {config.GOOGLE_CREDENTIALS_PATH}. "
            "Download them from Google Cloud Console (APIs & Services > Credentials, "
            "Desktop app OAuth client) and save them there first."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(config.GOOGLE_CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        raise AgentError(
            "Google auth completed but no refresh token was returned. Revoke app access in your "
            "Google Account (myaccount.google.com/permissions) and run `auth setup` again."
        )
    config.GOOGLE_TOKEN_PATH.write_text(creds.to_json())


def get_credentials() -> Credentials:
    if not config.GOOGLE_TOKEN_PATH.exists():
        raise NotAuthenticatedError("Not authenticated with Google yet. Run `python -m agent.cli auth setup` first.")

    creds = Credentials.from_authorized_user_file(str(config.GOOGLE_TOKEN_PATH), SCOPES)
    if creds.expired:
        if not creds.refresh_token:
            raise ReauthRequiredError(
                "Google credentials expired and no refresh token is available. "
                "Run `python -m agent.cli auth setup` again."
            )
        try:
            creds.refresh(Request())
        except RefreshError as exc:
            raise ReauthRequiredError(
                f"Google auth refresh failed (token likely revoked): {exc}. "
                "Run `python -m agent.cli auth setup` again."
            ) from exc
        config.GOOGLE_TOKEN_PATH.write_text(creds.to_json())
    return creds
