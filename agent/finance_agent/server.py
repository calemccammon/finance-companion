"""The HTTP service the app talks to.

A question or a client message is sent as a POST, and the answer comes back
on the same response as Server-Sent Events: one A2UI message per event, in
order.
"""

import json
import logging
import os
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


def _stream(messages: Iterable[dict]) -> StreamingResponse:
    def events() -> Iterator[str]:
        for message in messages:
            yield f"data: {json.dumps(message)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/ask")
def ask(question: Question) -> StreamingResponse:
    return _stream(agent().answer(question.text))


@app.post("/action")
def action(message: dict) -> StreamingResponse:
    """A2UI client-to-server messages: `action` from a tap, `error` from the renderer."""
    return _stream(agent().act(message))
