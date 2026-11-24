"""The Python SDK builds a v0.9.1 surface that the app's catalog accepts,
and it is the same surface the app's renderer test draws."""

import json
from pathlib import Path

import pytest
from a2ui.core.exceptions import A2uiValidationError
from a2ui.core.schema.v0_9 import (
    CreateSurface,
    CreateSurfaceMessage,
    UpdateComponents,
    UpdateComponentsMessage,
    UpdateDataModel,
    UpdateDataModelMessage,
)
from a2ui.utils.renderer_state import validate_payload

from finance_agent.catalog import load_catalog

FIXTURE = Path(__file__).resolve().parents[2] / "catalog" / "fixtures" / "metric-card-surface.jsonl"
CATALOG_ID = "https://github.com/calemccammon/finance-companion/catalog/v1"


def build_surface() -> list[dict]:
    components = [
        {"id": "root", "component": "Column", "children": ["title", "close"]},
        {"id": "title", "component": "Text", "text": "Apple", "variant": "h3"},
        {"id": "close", "component": "MetricCard", "label": "Close", "value": {"path": "/close"}},
    ]
    messages = [
        CreateSurfaceMessage(version="v0.9.1", create_surface=CreateSurface(surface_id="s1", catalog_id=CATALOG_ID)),
        UpdateComponentsMessage(
            version="v0.9.1", update_components=UpdateComponents(surface_id="s1", components=components)
        ),
        UpdateDataModelMessage(
            version="v0.9.1", update_data_model=UpdateDataModel(surface_id="s1", path="/close", value=182.31)
        ),
    ]
    return [m.model_dump(by_alias=True, exclude_none=True, mode="json") for m in messages]


def test_the_sdk_builds_the_surface_the_app_draws():
    built = build_surface()
    expected = [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]
    assert built == expected


def test_the_app_catalog_accepts_it():
    validate_payload([load_catalog()], build_surface())


def test_the_app_catalog_rejects_a_component_it_does_not_have():
    surface = build_surface()
    surface[1]["updateComponents"]["components"][2]["component"] = "Sparkline"
    with pytest.raises(A2uiValidationError, match="Sparkline"):
        validate_payload([load_catalog()], surface)


def test_the_app_catalog_rejects_a_card_without_its_figure():
    surface = build_surface()
    del surface[1]["updateComponents"]["components"][2]["value"]
    with pytest.raises(A2uiValidationError):
        validate_payload([load_catalog()], surface)


def test_the_app_s_action_message_is_one_the_sdk_reads():
    from a2ui.core.schema.v0_9.client_to_server import A2uiClientActionMessage

    fixture = Path(__file__).resolve().parents[2] / "catalog" / "fixtures" / "refresh-action.json"
    message = A2uiClientActionMessage.model_validate_json(fixture.read_text())

    assert message.action.name == "refresh"
    assert message.action.context == {"ticker": "AAPL"}


def test_the_app_catalog_accepts_the_component_fixture_the_app_draws():
    fixture = Path(__file__).resolve().parents[2] / "catalog" / "fixtures" / "components-surface.jsonl"
    validate_payload([load_catalog()], [json.loads(line) for line in fixture.read_text().splitlines() if line.strip()])
