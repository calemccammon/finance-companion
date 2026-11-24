"""The rules the SDK cannot check: bindings resolve, data lists are bound, and no figure is written by the model."""

import pytest

from finance_agent.checks import SurfaceRejected, check_surface, resolve

DATA = {
    "r1": {
        "latest": {"close": 182.31, "changePct": -4.2},
        "points": [{"date": "2026-11-19", "close": 181.0}, {"date": "2026-11-20", "close": 182.31}],
        "name": "Apple Inc.",
    }
}


def card(value, **extra):
    return {"id": "c", "component": "MetricCard", "label": "Close", "value": value, **extra}


def test_a_surface_bound_to_the_data_passes():
    check_surface(
        [
            {"id": "root", "component": "Column", "children": ["t", "c"], "weight": 1},
            {"id": "t", "component": "Text", "text": "Apple over the last 90 days, 10-year view"},
            card({"path": "/r1/latest/close"}),
        ],
        DATA,
    )


def test_json_pointers_resolve_through_objects_and_lists():
    assert resolve(DATA, "/r1/points/1/close") == (True, 182.31)
    assert resolve(DATA, "/r1/points/2/close")[0] is False
    assert resolve(DATA, "/r9")[0] is False
    assert resolve(DATA, "/") == (True, DATA)


def test_a_binding_to_nothing_is_rejected():
    with pytest.raises(SurfaceRejected, match="'/r1/latest/open', which is not in the data"):
        check_surface([card({"path": "/r1/latest/open"})], DATA)


def test_a_figure_typed_into_a_property_is_rejected():
    with pytest.raises(SurfaceRejected, match=r"writes the number 182\.31 in value"):
        check_surface([card(182.31)], DATA)


@pytest.mark.parametrize(
    "text",
    ["Apple closed at 182.31", "Down 4.2 this week", "Apple is at $183", "Up 5% since June", "A close of 182.3"],
)
def test_a_figure_written_in_text_is_rejected(text):
    with pytest.raises(SurfaceRejected, match="never in text"):
        check_surface([{"id": "t", "component": "Text", "text": text}], DATA)


@pytest.mark.parametrize("text", ["The last 90 days", "10-year Treasury yield", "Top 3 movers", "Q3 2026"])
def test_plain_counts_and_names_in_text_are_allowed(text):
    check_surface([{"id": "t", "component": "Text", "text": text}], DATA)


def test_paths_in_a_list_template_are_read_from_each_item():
    template = [
        {"id": "root", "component": "List", "children": {"componentId": "row", "path": "/r1/points"}},
        {"id": "row", "component": "Row", "children": ["d", "v"]},
        {"id": "d", "component": "Text", "text": {"path": "date"}},
        {"id": "v", "component": "MetricCard", "label": "Close", "value": {"path": "close"}},
    ]
    check_surface(template, DATA)

    template[3]["value"] = {"path": "open"}
    with pytest.raises(SurfaceRejected, match="'open'"):
        check_surface(template, DATA)


def test_a_template_over_something_that_is_not_a_list_is_rejected():
    with pytest.raises(SurfaceRejected, match="not a list"):
        check_surface(
            [{"id": "root", "component": "List", "children": {"componentId": "x", "path": "/r1/latest"}}], DATA
        )


def test_every_problem_is_named_at_once():
    with pytest.raises(SurfaceRejected) as e:
        check_surface([card({"path": "/nope"}), {"id": "t", "component": "Text", "text": "at 182.31"}], DATA)
    assert "'/nope'" in str(e.value) and "182.31" in str(e.value)


@pytest.mark.parametrize(
    "points",
    ["/r1/points", [{"date": "2026-11-20", "close": 182.31}]],
    ids=["a path written as text", "points written out"],
)
def test_a_chart_whose_points_are_not_bound_is_rejected(points):
    chart = {"id": "chart", "component": "PriceChart", "points": points}
    with pytest.raises(SurfaceRejected, match=r"writes its points as .*bind it to a list in the data"):
        check_surface([chart], DATA)


def test_a_chart_bound_to_its_points_passes():
    check_surface([{"id": "chart", "component": "PriceChart", "points": {"path": "/r1/points"}}], DATA)


RANKED = {
    "r1": {
        "rows": [
            {"ticker": "NVDA", "name": "NVIDIA", "returnPct": 12.5},
            {"ticker": "AAPL", "name": "Apple", "returnPct": -4.2},
        ]
    }
}


def row_card(label, index=0):
    return {"id": "c", "component": "MetricCard", "label": label, "value": {"path": f"/r1/rows/{index}/returnPct"}}


@pytest.mark.parametrize("label", ["AAPL return", "Apple", "Return"])
def test_a_card_showing_a_row_under_another_name_is_rejected(label):
    with pytest.raises(SurfaceRejected, match="shows row 0 of /r1/rows, which is NVDA / NVIDIA"):
        check_surface([row_card(label)], RANKED)


@pytest.mark.parametrize("label", ["NVDA return", "Nvidia since June", {"path": "/r1/rows/0/name"}])
def test_a_card_naming_its_row_passes(label):
    check_surface([row_card(label)], RANKED)


def test_a_short_ticker_must_be_a_word_of_the_label():
    visa = {"r1": {"rows": [{"ticker": "V", "name": "Visa", "returnPct": 3.1}]}}
    with pytest.raises(SurfaceRejected, match="which is V / Visa"):
        check_surface([row_card("Value since June")], visa)
    check_surface([row_card("V since June")], visa)


def test_a_label_bound_to_another_row_is_rejected():
    with pytest.raises(SurfaceRejected, match="shows row 1"):
        check_surface([row_card({"path": "/r1/rows/0/name"}, index=1)], RANKED)


@pytest.mark.parametrize(
    "text", ["Apple's last close was $/r1/latest/close", "Close: ${latest/close}", "Close: {{r1.latest.close}}"]
)
def test_a_path_written_into_text_is_rejected(text):
    with pytest.raises(SurfaceRejected, match="where it is shown as it is"):
        check_surface([{"id": "t", "component": "Text", "text": text}], DATA)


@pytest.mark.parametrize("text", ["Prices in USD/share", "Returns 2025/2026", "1/2 of the index"])
def test_a_slash_in_plain_text_is_allowed(text):
    check_surface([{"id": "t", "component": "Text", "text": text}], DATA)
