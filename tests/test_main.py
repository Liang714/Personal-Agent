from unittest.mock import patch

from fastapi.testclient import TestClient

from agent.api.main import app
from agent.errors import GoogleApiUnavailableError

client = TestClient(app)


@patch("agent.capabilities.calendar._get_provider")
def test_google_api_unavailable_maps_to_503(mock_get_provider):
    mock_get_provider.side_effect = GoogleApiUnavailableError("Couldn't reach Google Calendar")

    response = client.get("/calendar/events")

    assert response.status_code == 503
    assert response.json() == {"error": "Couldn't reach Google Calendar"}


@patch("agent.core.agent_loop.anthropic_client")
def test_chat_model_unavailable_maps_to_503(mock_anthropic_client):
    mock_anthropic_client.messages.create.side_effect = ConnectionError("boom")

    response = client.post("/chat", json={"message": "hi"})

    assert response.status_code == 503
    assert "Anthropic" in response.json()["error"]
