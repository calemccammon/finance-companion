"""The HTTP service: a question and an action are answered as Server-Sent Events."""

import json

import pytest
from conftest import calls, layout
from fastapi.testclient import TestClient

from finance_agent import server


def events(response) -> list[dict]:
    return [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def client(make_agent, monkeypatch):
    agent, _ = make_agent(
        calls(("price_history", {"ticker": "AAPL"})),
        layout("answer-1", {"id": "root", "component": "PriceChart", "points": {"path": "/r1/points"}}),
    )
    monkeypatch.setattr(server, "agent", lambda: agent)
    return TestClient(server.app)


def test_a_question_streams_a_surface(client):
    response = client.post("/ask", json={"text": "How is Apple doing?"})

    assert response.headers["content-type"].startswith("text/event-stream")
    assert [next(k for k in m if k != "version") for m in events(response)] == [
        "createSurface",
        "updateDataModel",
        "updateComponents",
    ]


def test_an_action_streams_its_answer(client):
    client.post("/ask", json={"text": "How is Apple doing?"})
    action = {
        "version": "v0.9.1",
        "action": {
            "name": "set_range",
            "surfaceId": "answer-1",
            "sourceComponentId": "b",
            "timestamp": "2026-11-23T12:00:00Z",
            "context": {"result": "/r1", "days": 30},
        },
    }

    sent = events(client.post("/action", json=action))

    assert sent[0]["updateDataModel"]["path"] == "/r1"
