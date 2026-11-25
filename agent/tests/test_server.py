"""The HTTP service: a question and an action are answered as Server-Sent Events."""

import json
import time

import pytest
from conftest import calls, layout
from fastapi.testclient import TestClient

from finance_agent import server


def events(response) -> list[dict]:
    """The A2UI messages of a response: its plain `data` events."""
    blocks = response.text.strip().split("\n\n")
    return [json.loads(b.removeprefix("data: ")) for b in blocks if b.startswith("data: ")]


def questions(response) -> list[str]:
    blocks = response.text.strip().split("\n\n")
    return [json.loads(b.split("\ndata: ")[1]) for b in blocks if b.startswith("event: question")]


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
    assert questions(response) == ["How is Apple doing?"]
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


def slow(messages, pause):
    for message in messages:
        time.sleep(pause)
        yield message


def test_while_the_agent_works_a_comment_keeps_the_stream_alive():
    messages = [{"question": "Hi"}, {"createSurface": {"surfaceId": "answer-1"}}]
    sent = list(server.sse_events(slow(messages, 0.25), keepalive=0.05))

    assert sent.count(server.KEEPALIVE) >= 4
    data = [e for e in sent if e != server.KEEPALIVE]
    assert data == ['event: question\ndata: "Hi"\n\n', 'data: {"createSurface": {"surfaceId": "answer-1"}}\n\n']
    assert server.KEEPALIVE.startswith(":")  # a comment, which a client skips


def test_a_quick_answer_has_no_comments():
    sent = list(server.sse_events([{"question": "Hi"}], keepalive=5))
    assert sent == ['event: question\ndata: "Hi"\n\n']


def test_an_error_while_answering_still_ends_the_stream_with_it():
    def failing():
        yield {"question": "Hi"}
        raise RuntimeError("the model is gone")

    stream = server.sse_events(failing(), keepalive=5)
    assert next(stream).startswith("event: question")
    with pytest.raises(RuntimeError, match="the model is gone"):
        next(stream)
