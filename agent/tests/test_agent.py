"""The agent with a scripted model: question to surface, checks and correction, actions."""

import json

from conftest import calls, layout

from finance_agent.agent import FALLBACK_TEXT, Agent
from finance_agent.model import ModelTurn, ScriptedClient, ToolTurn


def kinds(messages):
    return [next(k for k in m if k != "version") for m in messages if "question" not in m]


def answer(agent, question):
    """The A2UI messages of an answer, after the item naming the question."""
    items = list(agent.answer(question))
    assert items[0] == {"question": question}
    return items[1:]


APPLE_CARD = {
    "id": "c",
    "component": "MetricCard",
    "label": "Close",
    "value": {"path": "/r1/latest/close"},
    "format": "currency",
}


def test_a_question_becomes_a_surface_bound_to_the_tool_results(make_agent):
    agent, _ = make_agent(
        calls(("price_history", {"ticker": "AAPL"})),
        layout(
            "answer-1",
            {"id": "root", "component": "Column", "children": ["t", "c", "chart"]},
            {"id": "t", "component": "Text", "text": "Apple", "variant": "h3"},
            APPLE_CARD,
            {"id": "chart", "component": "PriceChart", "points": {"path": "/r1/points"}},
        ),
    )

    messages = answer(agent, "How is Apple doing?")

    assert kinds(messages) == ["createSurface", "updateDataModel", "updateComponents"]
    data = messages[1]["updateDataModel"]["value"]
    assert data["r1"]["ticker"] == "AAPL"
    assert data["r1"]["latest"]["close"] == 342.56
    assert [c["id"] for c in messages[2]["updateComponents"]["components"]] == ["root", "t", "c", "chart"]


def test_the_model_sees_where_each_result_is_and_a_short_preview(make_agent):
    agent, model = make_agent(
        calls(("price_history", {"ticker": "AAPL"})),
        layout("answer-1", APPLE_CARD | {"id": "root"}),
    )
    answer(agent, "How is Apple doing?")

    tool_turn = next(t for t in model.seen[1][1] if isinstance(t, ToolTurn))
    assert tool_turn.result["storedAt"] == "/r1"
    points = tool_turn.result["data"]["points"]
    assert points["rows"] > 5 and len(points["first"]) == 3


def test_the_system_prompt_carries_the_rules_and_the_catalog(make_agent):
    agent, model = make_agent(layout("answer-1", {"id": "root", "component": "Text", "text": "Hello"}))
    answer(agent, "Hi")

    system = model.seen[0][0]
    assert "Never write a number yourself" in system
    assert '"answer-1"' in system
    assert "RankedBars" in system and "PriceChart" in system


def test_a_tool_error_is_shown_to_the_model_which_can_try_again(make_agent):
    agent, model = make_agent(
        calls(("price_history", {"ticker": "APPLE"})),
        calls(("price_history", {"ticker": "AAPL"})),
        layout("answer-1", APPLE_CARD | {"id": "root"}),
    )
    messages = answer(agent, "How is Apple doing?")

    first_result = next(t for t in model.seen[1][1] if isinstance(t, ToolTurn)).result
    assert "Unknown ticker" in first_result["error"]
    # The failed call stored nothing, so the good one is /r1.
    assert list(messages[1]["updateDataModel"]["value"]) == ["r1"]


def test_a_rejected_surface_goes_back_to_the_model_once_with_the_reasons(make_agent):
    agent, model = make_agent(
        calls(("price_history", {"ticker": "AAPL"})),
        layout("answer-1", {"id": "root", "component": "Text", "text": "Apple closed at 342.56"}),
        layout("answer-1", APPLE_CARD | {"id": "root"}),
    )
    messages = answer(agent, "How is Apple doing?")

    correction = model.seen[2][1][-1]
    assert "rejected" in correction.text and "342.56" in correction.text
    assert messages[2]["updateComponents"]["components"][0]["component"] == "MetricCard"


def test_a_second_rejection_is_answered_with_a_plain_message(make_agent):
    bad = layout("answer-1", {"id": "root", "component": "Sparkline"})
    agent, model = make_agent(calls(("macro_snapshot", {})), bad, bad)

    messages = answer(agent, "How is the economy?")

    assert messages[2]["updateComponents"]["components"] == [{"id": "root", "component": "Text", "text": FALLBACK_TEXT}]
    assert len(model.seen) == 3


def test_a_model_that_never_stops_calling_tools_is_told_to_answer(make_agent):
    loop = calls(("macro_snapshot", {}))
    agent, model = make_agent(
        loop, loop, loop, loop, layout("answer-1", {"id": "root", "component": "Text", "text": "Done"})
    )

    messages = answer(agent, "How is the economy?")

    assert "do not call more tools" in model.seen[-1][1][-1].text
    assert messages[2]["updateComponents"]["components"][0]["text"] == "Done"


def test_a_layout_for_another_surface_is_corrected(make_agent):
    agent, model = make_agent(
        layout("answer-9", {"id": "root", "component": "Text", "text": "Hi"}),
        layout("answer-1", {"id": "root", "component": "Text", "text": "Hi"}),
    )
    messages = answer(agent, "Hi")
    assert "answer-9" in model.seen[1][1][-1].text
    assert messages[2]["updateComponents"]["surfaceId"] == "answer-1"


def test_two_layouts_in_one_answer_are_rejected(make_agent):
    hello = {
        "version": "v0.9.1",
        "updateComponents": {
            "surfaceId": "answer-1",
            "components": [{"id": "root", "component": "Text", "text": "Hi"}],
        },
    }
    twice = ModelTurn(text=f"<a2ui-json>{json.dumps([hello, hello])}</a2ui-json>")
    agent, model = make_agent(twice, layout("answer-1", {"id": "root", "component": "Text", "text": "Hi"}))

    answer(agent, "Hi")

    assert "exactly one updateComponents" in model.seen[1][1][-1].text


def test_set_range_reruns_the_tool_without_the_model(make_agent):
    agent, model = make_agent(
        calls(("price_history", {"ticker": "AAPL"})),
        layout("answer-1", APPLE_CARD | {"id": "root"}),
    )
    answer(agent, "How is Apple doing?")
    asked = len(model.seen)

    action = {
        "version": "v0.9.1",
        "action": {"name": "set_range", "surfaceId": "answer-1", "context": {"result": "/r1", "days": 30}},
    }
    messages = list(agent.act(action))

    assert len(model.seen) == asked
    assert kinds(messages) == ["updateDataModel"]
    update = messages[0]["updateDataModel"]
    assert update["path"] == "/r1"
    assert update["value"]["start"] >= "2026-10-21"
    # Kept, so a later correction or range change starts from it.
    surface = agent.surface("answer-1")
    assert surface.data["r1"] == update["value"]
    assert surface.results["/r1"][1]["start"] == "2026-10-21"


def test_set_range_with_a_bad_context_does_nothing(make_agent):
    agent, _ = make_agent(calls(("price_history", {"ticker": "AAPL"})), layout("answer-1", APPLE_CARD | {"id": "root"}))
    answer(agent, "How is Apple doing?")

    for context in ({"result": "/r9", "days": 30}, {"result": "/r1", "days": 9999}, {"result": "/r1", "days": "30"}):
        assert list(agent.act({"action": {"name": "set_range", "surfaceId": "answer-1", "context": context}})) == []


def test_pressing_a_ticker_asks_about_it_on_a_new_surface(make_agent):
    agent, model = make_agent(
        calls(("volatility_rank", {})),
        layout(
            "answer-1",
            {
                "id": "root",
                "component": "RankedBars",
                "rows": {"path": "/r1/rows"},
                "valueKey": "volatility",
                "format": "percent",
                "rowAction": "open_ticker",
            },
        ),
        calls(("price_history", {"ticker": "TSLA"})),
        layout("answer-2", {"id": "root", "component": "PriceChart", "points": {"path": "/r1/points"}}),
    )
    answer(agent, "Which stocks are most volatile?")

    messages = list(
        agent.act({"action": {"name": "open_ticker", "surfaceId": "answer-1", "context": {"ticker": "TSLA"}}})
    )

    assert messages[0] == {"question": "How is TSLA doing?"}
    assert messages[1]["createSurface"]["surfaceId"] == "answer-2"
    assert "TSLA" in model.seen[2][1][0].text


def test_an_error_from_the_renderer_is_corrected_once(make_agent):
    agent, model = make_agent(
        calls(("price_history", {"ticker": "AAPL"})),
        layout("answer-1", APPLE_CARD | {"id": "root"}),
        layout("answer-1", {"id": "root", "component": "Text", "text": "Fixed"}),
    )
    answer(agent, "How is Apple doing?")

    error = {
        "version": "v0.9.1",
        "error": {"code": "VALIDATION_FAILED", "surfaceId": "answer-1", "message": "type mismatch"},
    }
    messages = list(agent.act(error))
    assert messages[0]["updateComponents"]["components"][0]["text"] == "Fixed"
    assert "type mismatch" in model.seen[-1][1][-1].text

    # The correction is spent: a second error is only logged.
    assert list(agent.act(error)) == []


def test_unknown_actions_are_ignored(make_agent):
    agent, _ = make_agent()
    assert list(agent.act({"action": {"name": "launch", "surfaceId": "x"}})) == []
    assert list(agent.act({"action": {"name": "set_range", "surfaceId": "nope", "context": {}}})) == []


def test_conversational_text_with_figures_is_never_sent(make_agent):
    # The text around the JSON block is dropped, so a figure there cannot reach the screen.
    agent, _ = make_agent(
        calls(("price_history", {"ticker": "AAPL"})),
        ModelTurn(
            text=layout("answer-1", APPLE_CARD | {"id": "root"}).text.replace("Here you go.", "Apple closed at 342.56.")
        ),
    )
    messages = answer(agent, "How is Apple doing?")
    assert "342.56" not in str(messages[2])


def test_a_reply_that_is_not_json_is_corrected(make_agent):
    agent, model = make_agent(
        ModelTurn(text='<a2ui-json>[{"version": "v0.9.1", "updateComponents": </a2ui-json>'),
        layout("answer-1", {"id": "root", "component": "Text", "text": "Hi"}),
    )
    messages = answer(agent, "Hi")
    assert "rejected" in model.seen[1][1][-1].text
    assert messages[2]["updateComponents"]["components"][0]["text"] == "Hi"


def test_a_reply_with_no_layout_at_all_is_corrected(make_agent):
    agent, model = make_agent(
        ModelTurn(text="Apple is doing fine."),
        layout("answer-1", {"id": "root", "component": "Text", "text": "Hi"}),
    )
    answer(agent, "Hi")
    assert "exactly one updateComponents" in model.seen[1][1][-1].text


def bare(surface, *components):
    """A reply held to the layout's schema: the bare message, with no block around it."""
    return ModelTurn(
        text=json.dumps(
            {"version": "v0.9.1", "updateComponents": {"surfaceId": surface, "components": list(components)}}
        )
    )


def test_a_model_that_follows_a_schema_gathers_with_tools_then_lays_out_under_the_schema(warehouse, catalog):
    model = ScriptedClient(
        [
            calls(("price_history", {"ticker": "AAPL"})),
            ModelTurn(text="Apple closed at 342.56."),  # its free-written answer: dropped
            bare("answer-1", APPLE_CARD | {"id": "root"}),
        ],
        follows_schema=True,
    )
    messages = answer(Agent(warehouse, catalog, model), "How is Apple doing?")

    assert messages[2]["updateComponents"]["components"][0]["component"] == "MetricCard"
    tools, schemas = zip(*model.offered, strict=True)
    # Tools while gathering; then the same request again, held to the schema, with none.
    assert [bool(t) for t in tools] == [True, True, False]
    assert schemas[:2] == (None, None)
    assert schemas[2]["properties"]["updateComponents"]["properties"]["surfaceId"] == {"const": "answer-1"}
    # The layout may only bind to what was fetched.
    assert "/r1/latest/close" in schemas[2]["$defs"]["NumberBinding"]["properties"]["path"]["enum"]
    assert model.seen[2][1] == model.seen[1][1]
    assert all("342.56" not in getattr(turn, "text", "") for turn in model.seen[2][1])


def test_a_correction_is_held_to_the_schema_too(warehouse, catalog):
    model = ScriptedClient(
        [
            calls(("price_history", {"ticker": "AAPL"})),
            ModelTurn(text="done"),
            bare("answer-1", APPLE_CARD | {"id": "root", "value": {"path": "/r1/latest/open"}}),
            bare("answer-1", APPLE_CARD | {"id": "root"}),
        ],
        follows_schema=True,
    )
    messages = answer(Agent(warehouse, catalog, model), "How is Apple doing?")

    assert model.offered[3][0] == [] and model.offered[3][1] is not None
    assert "/r1/latest/open" in model.seen[3][1][-1].text
    assert messages[2]["updateComponents"]["components"][0]["value"] == {"path": "/r1/latest/close"}


def test_the_schema_can_be_turned_off_for_a_model_that_follows_one(warehouse, catalog):
    model = ScriptedClient([layout("answer-1", {"id": "root", "component": "Text", "text": "Hi"})], follows_schema=True)
    answer(Agent(warehouse, catalog, model, use_schema=False), "Hi")
    assert model.offered[0][1] is None
