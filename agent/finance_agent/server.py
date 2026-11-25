"""The HTTP service the app talks to.

A question or a client message is sent as a POST, and the answer comes back
on the same response as Server-Sent Events: one A2UI message per event, in
order.

A local model can take minutes over one answer, sending nothing meanwhile. So
while the agent works, a comment line goes out every few seconds: the app's
client skips it, as the standard says, but it shows the connection is alive,
and the app's read timeout fires only if the agent has stopped.
"""

import json
import logging
import os
import queue
import threading
from collections.abc import Iterable, Iterator
from functools import lru_cache

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from finance_agent.agent import Agent
from finance_agent.catalog import load_catalog
from finance_agent.model import client_from_env
from finance_agent.warehouse import Warehouse

logging.basicConfig(level=os.environ.get("FC_LOG_LEVEL", "INFO"))
app = FastAPI(title="finance-companion agent")


@lru_cache(maxsize=1)
def agent() -> Agent:
    return Agent(Warehouse(), load_catalog(), client_from_env())


class Question(BaseModel):
    text: str


# Seconds between comment lines while the agent works: well under the app's read timeout.
KEEPALIVE_SECONDS = 15.0
KEEPALIVE = ": working\n\n"


def sse_events(messages: Iterable[dict], keepalive: float = KEEPALIVE_SECONDS) -> Iterator[str]:
    """A2UI messages as `data` events; the question an answer is for as a `question` event;
    and a comment after each [keepalive] seconds with no message."""
    pending: queue.Queue = queue.Queue()
    done = object()

    def produce() -> None:
        try:
            for message in messages:
                pending.put(message)
        except Exception as e:  # handed to the reader, which raises it
            pending.put(e)
        finally:
            pending.put(done)

    threading.Thread(target=produce, daemon=True).start()
    while True:
        try:
            item = pending.get(timeout=keepalive)
        except queue.Empty:
            yield KEEPALIVE
            continue
        if item is done:
            return
        if isinstance(item, Exception):
            raise item
        if set(item) == {"question"}:
            yield f"event: question\ndata: {json.dumps(item['question'])}\n\n"
        else:
            yield f"data: {json.dumps(item)}\n\n"


def _stream(messages: Iterable[dict]) -> StreamingResponse:
    return StreamingResponse(sse_events(messages), media_type="text/event-stream")


@app.post("/ask")
def ask(question: Question) -> StreamingResponse:
    return _stream(agent().answer(question.text))


@app.post("/action")
def action(message: dict) -> StreamingResponse:
    """A2UI client-to-server messages: `action` from a tap, `error` from the renderer."""
    return _stream(agent().act(message))
