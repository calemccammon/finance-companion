import json

import pytest

from finance_agent.agent import Agent
from finance_agent.catalog import load_catalog
from finance_agent.model import ModelTurn, ScriptedClient, ToolCall
from finance_agent.warehouse import Warehouse


@pytest.fixture(scope="session")
def warehouse():
    wh = Warehouse()
    yield wh
    wh.close()


@pytest.fixture(scope="session")
def catalog():
    return load_catalog()


def calls(*pairs) -> ModelTurn:
    """A model turn that calls tools: calls(("price_history", {"ticker": "AAPL"}), ...)."""
    return ModelTurn(tool_calls=tuple(ToolCall(name=n, arguments=a) for n, a in pairs))


def layout(surface: str, *components: dict, text: str = "Here you go.") -> ModelTurn:
    """A model turn answering with one updateComponents message."""
    message = {"version": "v0.9.1", "updateComponents": {"surfaceId": surface, "components": list(components)}}
    return ModelTurn(text=f"{text}\n<a2ui-json>{json.dumps([message])}</a2ui-json>")


@pytest.fixture
def make_agent(warehouse, catalog):
    def make(*replies: ModelTurn) -> tuple[Agent, ScriptedClient]:
        model = ScriptedClient(list(replies))
        return Agent(warehouse, catalog, model), model

    return make
