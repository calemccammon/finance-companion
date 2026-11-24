"""The evaluation harness, scored against scripted models whose behaviour is known."""

import json
from dataclasses import asdict

from conftest import calls, layout

from evals.run import QUESTIONS, SCORES, failure_class, report, run_question, summarise
from finance_agent.model import ModelTurn, ScriptedClient

CARD = {"id": "root", "component": "MetricCard", "label": "Close", "value": {"path": "/r1/latest/close"}}
APPLE = {"id": "aapl-how", "ask": "How is Apple doing?", "tools": ["price_history"], "tickers": ["AAPL"]}
OFF_TOPIC = {"id": "poem", "ask": "Write me a poem.", "tools": [], "tickers": []}


def test_the_question_set_is_well_formed():
    questions = json.loads(QUESTIONS.read_text())
    tools = {
        "company_profile",
        "price_history",
        "compare_returns",
        "volatility_rank",
        "macro_overlay",
        "macro_snapshot",
    }
    assert len(questions) >= 50
    assert len({q["id"] for q in questions}) == len(questions)
    for q in questions:
        assert set(q["tools"]) <= tools, q["id"]


def test_a_clean_answer_scores_on_every_count(warehouse, catalog):
    model = ScriptedClient([calls(("price_history", {"ticker": "AAPL"})), layout("answer-1", CARD)])
    outcome = run_question(APPLE, model, warehouse, catalog)
    assert all(outcome.scores.values()), outcome.scores
    assert outcome.tools == ["price_history"]


def test_a_written_figure_corrected_on_the_second_try_renders_but_not_first_time(warehouse, catalog):
    model = ScriptedClient(
        [
            calls(("price_history", {"ticker": "AAPL"})),
            layout("answer-1", {"id": "root", "component": "Text", "text": "Apple closed at 342.56"}),
            layout("answer-1", CARD),
        ]
    )
    outcome = run_question(APPLE, model, warehouse, catalog)
    assert outcome.scores["renders"] and not outcome.scores["first_try"]
    assert not outcome.scores["no_written_figure"]
    assert outcome.rejections == [["written figure"]]


def test_two_bad_layouts_fall_back_and_do_not_render(warehouse, catalog):
    bad = layout("answer-1", {"id": "root", "component": "Sparkline"})
    model = ScriptedClient([calls(("price_history", {"ticker": "AAPL"})), bad, bad])
    outcome = run_question(APPLE, model, warehouse, catalog)
    assert outcome.fallback and not outcome.scores["renders"]
    assert not outcome.scores["catalog_only"]


def test_tools_are_scored_against_what_the_question_needs(warehouse, catalog):
    wrong = ScriptedClient(
        [calls(("macro_snapshot", {})), layout("answer-1", {"id": "root", "component": "Text", "text": "Hi"})]
    )
    assert not run_question(APPLE, wrong, warehouse, catalog).scores["right_tools"]

    none = ScriptedClient([layout("answer-1", {"id": "root", "component": "Text", "text": "I can help with stocks."})])
    assert run_question(OFF_TOPIC, none, warehouse, catalog).scores["right_tools"]


def test_a_model_that_fails_is_a_result_not_a_crash(warehouse, catalog):
    outcome = run_question(APPLE, ScriptedClient([]), warehouse, catalog)
    assert outcome.error and not outcome.scores["renders"]


def test_rejections_are_sorted_into_classes():
    assert failure_class("components.c.component: Unrecognized component type 'X'") == ["unknown component"]
    assert failure_class("binds value to '/r9', which is not in the data; writes the figure '1.0'") == [
        "missing data path",
        "written figure",
    ]
    # The SDK's own words, as a local model's layouts drew them.
    assert failure_class("The direct JSON block is not JSON: Invalid JSON at 412") == ["not JSON"]
    assert failure_class("Missing root component: No component has id='root'") == ["broken component tree"]
    assert failure_class("Component 'card-1' is not reachable from 'root'") == ["broken component tree"]
    assert failure_class("components.root.children: [{'id': 'h1', 'component': 'Text'}]") == [
        "components nested in children"
    ]
    assert failure_class("components.m1.value: '/r1/latest/close' is not valid under any of the given schemas") == [
        "path written as plain text"
    ]
    assert failure_class("updateComponents.weight\n  Extra inputs are not permitted") == ["stray fields"]
    # Both phrases somewhere, but no path rejected: not a plain-text path.
    assert "path written as plain text" not in failure_class(
        "children: [{'text': 'a: '/x'}] Extra inputs are not permitted; is not valid under any of the given schemas"
    )
    assert failure_class("something else") == ["other schema error"]


def test_the_report_counts_scores_and_failure_classes(warehouse, catalog):
    model = ScriptedClient(
        [
            calls(("price_history", {"ticker": "AAPL"})),
            layout("answer-1", {"id": "root", "component": "Text", "text": "At 342.56"}),
            layout("answer-1", CARD),
        ],
        name="scripted",
    )

    result = {"model": "scripted", "outcomes": [asdict(run_question(APPLE, model, warehouse, catalog))]}
    summary = summarise(result)
    assert summary["passed"]["renders"] == 1 and summary["passed"]["first_try"] == 0
    assert summary["failure_classes"] == {"written figure": 1}
    assert "writes the figure" in result["outcomes"][0]["reasons"][0]
    text = report([result])
    assert "| scripted | 1 | 1 | 1 | 0 |" in text
    assert "| scripted | written figure | 1 |" in text
    # Two attempts: one rejected by the app's own check, then one that rendered.
    assert summary["attempts"] == 2 and summary["reached_own_checks"] == 2
    assert "| scripted | 2 | 2 |" in text


def test_conversational_text_is_not_needed_for_a_layout():
    assert isinstance(layout("answer-1", CARD), ModelTurn)


def test_saved_reasons_are_sorted_by_todays_rules():
    outcome = {"accepted": False, "rejections": [["other schema error"]], "reasons": ["The JSON block is not JSON"]}
    summary = summarise({"model": "m", "outcomes": [outcome | {"scores": dict.fromkeys(SCORES, False)}]})
    assert summary["failure_classes"] == {"not JSON": 1}
    assert summary["attempts"] == 1 and summary["reached_own_checks"] == 0


def test_a_screen_with_no_data_on_it_renders_but_does_not_show_data(warehouse, catalog):
    heading = {"id": "root", "component": "Text", "text": "Apple", "variant": "h3"}
    model = ScriptedClient([calls(("price_history", {"ticker": "AAPL"})), layout("answer-1", heading)])
    outcome = run_question(APPLE, model, warehouse, catalog)
    assert outcome.scores["renders"] and not outcome.scores["shows_data"]
    assert outcome.layout == [heading]


def test_a_bound_screen_shows_data_and_an_off_topic_answer_needs_none(warehouse, catalog):
    model = ScriptedClient([calls(("price_history", {"ticker": "AAPL"})), layout("answer-1", CARD)])
    assert run_question(APPLE, model, warehouse, catalog).scores["shows_data"]

    model = ScriptedClient([layout("answer-1", {"id": "root", "component": "Text", "text": "I answer about stocks."})])
    assert run_question(OFF_TOPIC, model, warehouse, catalog).scores["shows_data"]
