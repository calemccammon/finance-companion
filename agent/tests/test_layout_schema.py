"""The schema a model's layout can be held to: real layouts pass, and each
mistake a local model made in the evaluations is impossible under it."""

import json
import re
from pathlib import Path

import jsonschema
import pytest

from finance_agent.agent import VERSION
from finance_agent.layout_schema import layout_schema

ROOT = Path(__file__).resolve().parents[2]


def validator(surface="answer-1"):
    return jsonschema.Draft202012Validator(layout_schema(surface, VERSION))


def message(*components, surface="answer-1", **extra):
    return {"version": VERSION, "updateComponents": {"surfaceId": surface, "components": list(components), **extra}}


def test_the_schema_is_valid_and_needs_no_other_file():
    schema = layout_schema("answer-1", VERSION)
    jsonschema.Draft202012Validator.check_schema(schema)
    text = json.dumps(schema)
    assert "common_types.json" not in text and "catalog.json" not in text
    assert "FunctionCall" not in text


def test_the_layout_both_halves_draw_passes():
    lines = (ROOT / "catalog" / "fixtures" / "components-surface.jsonl").read_text().splitlines()
    update = next(json.loads(line) for line in lines if "updateComponents" in line)
    assert validator(update["updateComponents"]["surfaceId"]).is_valid(update)


def test_the_demo_script_s_layouts_pass():
    script = json.loads((ROOT / "agent" / "demo" / "script.json").read_text())
    blocks = [re.search(r"<a2ui-json>(.*)</a2ui-json>", t["text"], re.S) for t in script if "text" in t]
    layouts = [json.loads(b.group(1))[0] for b in blocks if b]
    assert len(layouts) == 3
    for layout in layouts:
        assert validator(layout["updateComponents"]["surfaceId"]).is_valid(layout)


TEXT = {"id": "root", "component": "Text", "text": "Hi"}


@pytest.mark.parametrize(
    "layout",
    [
        message({"id": "root", "component": "Column", "children": [TEXT]}),
        message({"id": "m", "component": "MetricCard", "label": "Close", "value": "/r1/latest/close"}),
        message({"id": "m", "component": "MetricCard", "label": "Close", "value": 342.56}),
        message({"id": "r", "component": "RankedBars", "rows": "/r1/rows", "valueKey": "volatility"}),
        message(TEXT, weight=1),
        message(TEXT | {"type": "Column"}),
        message({"id": "root", "component": "Sparkline"}),
        message({"component": "Text", "text": "Hi"}),
        message(TEXT, surface="answer-9"),
        message(),
    ],
    ids=[
        "a component nested in children",
        "a path written as text",
        "a figure written out",
        "a ranking's rows written as text",
        "a stray field in the message",
        "a stray field on a component",
        "an unknown component",
        "a component without an id",
        "another surface",
        "no components",
    ],
)
def test_a_mistake_is_impossible_under_the_schema(layout):
    assert not validator().is_valid(layout)


def test_a_simple_correct_layout_passes():
    assert validator().is_valid(message(TEXT))
