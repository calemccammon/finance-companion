"""The HTTP service the app talks to.

A question or an action is sent as a POST, and the answer comes back on the
same response as Server-Sent Events: one A2UI message per event, in order.
The app sends its A2UI client capabilities with every request, so the agent
knows which catalogs it may use.
"""

import json
from collections.abc import Iterable, Iterator

from a2ui.utils.renderer_state import validate_payload
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from finance_agent.catalog import load_catalog
from finance_agent.spike import refreshed_close, surface_for

app = FastAPI(title="finance-companion agent")
catalog = load_catalog()


class Question(BaseModel):
    text: str
    a2uiClientCapabilities: dict | None = None


def _events(messages: Iterable[dict]) -> Iterator[str]:
    for message in messages:
        yield f"data: {json.dumps(message)}\n\n"


def _stream(messages: list[dict]) -> StreamingResponse:
    # Nothing reaches the app that its catalog would reject.
    validate_payload([catalog], messages, surface_catalog_ids={"s1": catalog.catalog_id})
    return StreamingResponse(_events(messages), media_type="text/event-stream")


@app.post("/ask")
def ask(question: Question) -> StreamingResponse:
    return _stream(surface_for(question.text))


@app.post("/action")
def action(message: dict) -> StreamingResponse:
    """A2UI client-to-server messages: `action` from a tap, `error` from the renderer."""
    if "error" in message:
        print("renderer reported:", message["error"])
        return _stream([])
    name = message["action"]["name"]
    print("action:", name, message["action"].get("context"))
    return _stream(refreshed_close() if name == "refresh" else [])
