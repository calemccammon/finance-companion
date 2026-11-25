"""The schema a model's layout can be held to: real layouts pass, and each
mistake a local model made in the evaluations is impossible under it."""

import json
import re
from pathlib import Path

import jsonschema
import pytest

from finance_agent.agent import VERSION
from finance_agent.layout_schema import layout_schema
from finance_agent.tools import run_tool

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
    # It shows what the app can draw, with hand-written labels, so it is held to the
    # catalog; a model's layout is also held to its data (below).
    update, _ = fixture()
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


DATA = fixture()[1]


# The labels a card must give these figures.
LABELS = {
    "/r1/latest/close": "Close",
    "/r1/latest/changePct": "Change over the range",
    "/r2/rows/0/returnPct": {"path": "/r2/rows/0/name"},
    "/r2/rows/1/returnPct": {"path": "/r2/rows/1/ticker"},
}


def metric(path, drawn="currency", label=None):
    label = label or LABELS.get(path, "Close")
    return {"id": "root", "component": "MetricCard", "label": label, "value": {"path": path}, "format": drawn}


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

    def card(index, drawn):
        return metric(f"/r1/rows/{index}/value", drawn, {"path": f"/r1/rows/{index}/name"})

    assert validator(data=data).is_valid(message(card(0, "number")))
    assert not validator(data=data).is_valid(message(card(0, "percent")))
    assert validator(data=data).is_valid(message(card(1, "percent")))
    assert not validator(data=data).is_valid(message(card(1, "number")))


@pytest.fixture(scope="module")
def apple(warehouse):
    return {"r1": run_tool(warehouse, "price_history", {"ticker": "AAPL"}).data}


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("/r1/latest/close", "Close"),
        ("/r1/latest/changePct", "Change over the range"),
        ("/r1/latest/dailyReturnPct", "Change on the day"),
        ("/r1/latest/volatility20d", "20-day volatility"),
        ("/r1/latest/position52w", "Place in 52-week range"),
    ],
)
def test_a_figure_can_only_carry_its_own_label(apple, path, label):
    from finance_agent.tools import figure_format

    drawn = figure_format(apple, path)
    assert validator(data=apple).is_valid(message(metric(path, drawn, label)))
    for wrong in ("52-Week Volatility", "Monthly Change", "Price", "Daily Return"):
        assert not validator(data=apple).is_valid(message(metric(path, drawn, wrong))), wrong


def test_a_latest_figure_s_caption_can_only_be_its_date(apple):
    card = metric("/r1/latest/close", "currency", "Close")
    assert validator(data=apple).is_valid(message(card))
    assert validator(data=apple).is_valid(message(card | {"caption": {"path": "/r1/end"}}))
    assert not validator(data=apple).is_valid(message(card | {"caption": {"path": "/r1/start"}}))
    assert not validator(data=apple).is_valid(message(card | {"caption": "20 November"}))


def test_a_row_s_card_shows_its_main_figure_under_its_own_name():
    rows = {
        "r1": {
            "end": "2026-11-20",
            "rows": [{"ticker": "NVDA", "name": "NVIDIA", "startClose": 1.0, "returnPct": 12.5}],
        }
    }
    card = metric("/r1/rows/0/returnPct", "change", {"path": "/r1/rows/0/name"})
    assert validator(data=rows).is_valid(message(card))
    assert not validator(data=rows).is_valid(message(card | {"label": "Apple"}))
    assert not validator(data=rows).is_valid(message(card | {"label": {"path": "/r1/rows/0/startClose"}}))
    # Its start close would carry the same label as its return, so it has no card.
    start = metric("/r1/rows/0/startClose", "currency", {"path": "/r1/rows/0/name"})
    assert not validator(data=rows).is_valid(message(start))


def test_a_figure_from_a_result_without_a_date_has_no_caption():
    overlay = {"r1": {"ticker": "MSFT", "seriesName": "Consumer price index", "latest": {"close": 484.52}}}
    card = metric("/r1/latest/close", "currency", "Close")
    assert validator(data=overlay).is_valid(message(card))
    assert not validator(data=overlay).is_valid(message(card | {"caption": "Today"}))
    assert not validator(data=overlay).is_valid(message(card | {"caption": {"path": "/r1/ticker"}}))
