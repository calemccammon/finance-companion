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


def validator(surface="answer-1", data=None):
    return jsonschema.Draft202012Validator(layout_schema(surface, VERSION, data))


def message(*components, surface="answer-1", **extra):
    return {"version": VERSION, "updateComponents": {"surfaceId": surface, "components": list(components), **extra}}


def test_the_schema_is_valid_and_needs_no_other_file():
    schema = layout_schema("answer-1", VERSION)
    jsonschema.Draft202012Validator.check_schema(schema)
    text = json.dumps(schema)
    assert "common_types.json" not in text and "catalog.json" not in text
    assert "FunctionCall" not in text


def fixture():
    """The layout both halves draw, and the data it binds to."""
    lines = [json.loads(line) for line in (ROOT / "catalog" / "fixtures" / "components-surface.jsonl").open()]
    update = next(m for m in lines if "updateComponents" in m)
    data = next(m for m in lines if "updateDataModel" in m)["updateDataModel"]["value"]
    return update, data


def test_the_layout_both_halves_draw_passes():
    update, data = fixture()
    surface = update["updateComponents"]["surfaceId"]
    assert validator(surface).is_valid(update)
    assert validator(surface, data).is_valid(update)


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


DATA = fixture()[1]


def metric(path, drawn="currency"):
    return {"id": "root", "component": "MetricCard", "label": "Close", "value": {"path": path}, "format": drawn}


@pytest.mark.parametrize(
    "layout",
    [
        message(metric("/r1/latest/open")),
        message(metric("/r1/points")),
        message(metric("/r1/ticker")),
        message({"id": "root", "component": "PriceChart", "points": {"path": "/r1/latest/close"}}),
        message({"id": "root", "component": "RankedBars", "rows": {"path": "/r9/rows"}, "valueKey": "returnPct"}),
        message({"id": "root", "component": "Text", "text": {"path": "/r1/latest/close"}}),
        message({"id": "root", "component": "Column", "children": {"componentId": "t", "path": "/r2/rows"}}),
    ],
    ids=[
        "a path not in the data",
        "a list where a number is drawn",
        "a word where a number is drawn",
        "a number where a chart's points are drawn",
        "a ranking of a result that does not exist",
        "a number bound as text",
        "children repeated over a list",
    ],
)
def test_with_the_data_a_binding_can_only_name_a_path_it_holds(layout):
    assert not validator(data=DATA).is_valid(layout)


def test_with_the_data_a_row_of_a_short_list_can_be_named():
    assert validator(data=DATA).is_valid(message(metric("/r2/rows/0/returnPct", "change")))
    assert validator(data=DATA).is_valid(message({"id": "root", "component": "Text", "text": {"path": "/r1/ticker"}}))


def test_a_point_of_a_long_list_cannot_be_named():
    data = {"r1": {"points": [{"close": float(i)} for i in range(100)]}}
    assert not validator(data=data).is_valid(message(metric("/r1/points/0/close")))


def test_without_data_an_answer_can_only_be_words():
    schema = layout_schema("answer-1", VERSION, {})
    jsonschema.Draft202012Validator.check_schema(schema)
    names = [
        c["properties"]["component"]["const"]
        for c in schema["properties"]["updateComponents"]["properties"]["components"]["items"]["anyOf"]
    ]
    assert "MetricCard" not in names and "PriceChart" not in names and "RankedBars" not in names
    assert "Text" in names
    assert validator(data={}).is_valid(message(TEXT))
    assert not validator(data={}).is_valid(message({"id": "root", "component": "Text", "text": {"path": "/r1/ticker"}}))


@pytest.mark.parametrize(
    ("path", "drawn"),
    [("/r1/latest/close", "currency"), ("/r1/latest/changePct", "change"), ("/r2/rows/1/returnPct", "change")],
)
def test_with_the_data_a_figure_can_only_be_drawn_in_its_format(path, drawn):
    assert validator(data=DATA).is_valid(message(metric(path, drawn)))
    for other in {"number", "currency", "percent", "change"} - {drawn}:
        assert not validator(data=DATA).is_valid(message(metric(path, other))), other
    card = metric(path, drawn)
    del card["format"]
    assert not validator(data=DATA).is_valid(message(card))


def test_a_ranking_s_format_is_tied_to_the_field_it_ranks_by():
    bars = {"id": "root", "component": "RankedBars", "rows": {"path": "/r2/rows"}, "valueKey": "returnPct"}
    assert validator(data=DATA).is_valid(message(bars | {"format": "change"}))
    assert not validator(data=DATA).is_valid(message(bars | {"format": "number"}))
    assert not validator(data=DATA).is_valid(message(bars | {"format": "change", "valueKey": "ticker"}))


def test_the_consumer_price_index_is_drawn_as_a_number_and_a_rate_as_a_percent():
    data = {
        "r1": {
            "rows": [
                {"series": "cpi", "name": "Consumer price index", "value": 337.476},
                {"series": "fed_funds_rate", "name": "Federal funds rate", "value": 3.88},
            ]
        }
    }
    assert validator(data=data).is_valid(message(metric("/r1/rows/0/value", "number")))
    assert not validator(data=data).is_valid(message(metric("/r1/rows/0/value", "percent")))
    assert validator(data=data).is_valid(message(metric("/r1/rows/1/value", "percent")))
    assert not validator(data=data).is_valid(message(metric("/r1/rows/1/value", "number")))
