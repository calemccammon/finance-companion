"""Spike for issue #3: the agent streams a surface and answers an action."""

import json

from fastapi.testclient import TestClient

from finance_agent.server import app

client = TestClient(app)


def events(response) -> list[dict]:
    return [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]


def test_a_question_streams_a_surface_as_server_sent_events():
    response = client.post("/ask", json={"text": "How is Apple doing?"})

    assert response.headers["content-type"].startswith("text/event-stream")
    sent = events(response)
    assert [next(k for k in m if k != "version") for m in sent] == ["createSurface", "updateComponents", "updateDataModel"]


def test_a_tap_on_refresh_rewrites_the_figure_only():
    response = client.post(
        "/action",
        json={"version": "v0.9.1", "action": {"name": "refresh", "surfaceId": "s1", "sourceComponentId": "refresh", "timestamp": "2026-11-23T12:00:00Z", "context": {"ticker": "AAPL"}}},
    )

    sent = events(response)
    assert len(sent) == 1
    assert sent[0]["updateDataModel"]["path"] == "/close"


def test_the_app_s_action_message_is_one_the_sdk_reads():
    from pathlib import Path

    from a2ui.core.schema.v0_9.client_to_server import A2uiClientActionMessage

    fixture = Path(__file__).resolve().parents[2] / "catalog" / "fixtures" / "refresh-action.json"
    message = A2uiClientActionMessage.model_validate_json(fixture.read_text())

    assert message.action.name == "refresh"
    assert message.action.context == {"ticker": "AAPL"}
