"""The evaluation harness, scored against scripted models whose behaviour is known."""

import json
from collections import Counter
from dataclasses import asdict

from conftest import calls, layout

from evals.run import QUESTIONS, failure_class, report, run_question, summarise
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
    from dataclasses import asdict

    result = {"model": "scripted", "outcomes": [asdict(run_question(APPLE, model, warehouse, catalog))]}
    summary = summarise(result)
    assert summary["passed"]["renders"] == 1 and summary["passed"]["first_try"] == 0
    assert summary["failure_classes"] == {"written figure": 1}
    text = report([result])
    assert "| scripted | 1 | 1 | 0 |" in text
    assert "| scripted | written figure | 1 |" in text


def test_conversational_text_is_not_needed_for_a_layout():
    assert isinstance(layout("answer-1", CARD), ModelTurn)


def test_the_tokens_a_counting_client_uses_are_kept_per_question_and_summed(warehouse, catalog):
    class Counting(ScriptedClient):
        def __init__(self, replies):
            super().__init__(replies, name="counting")
            self.usage = Counter()

        def reply(self, system, transcript, tools):
            self.usage.update(input_tokens=100, output_tokens=10)
            return super().reply(system, transcript, tools)

    model = Counting([calls(("price_history", {"ticker": "AAPL"})), layout("answer-1", CARD)] * 2)
    first, second = (asdict(run_question(APPLE, model, warehouse, catalog)) for _ in range(2))

    # Each question counts only its own two requests.
    assert first["tokens"] == second["tokens"] == {"input_tokens": 200, "output_tokens": 20}
    summary = summarise({"model": "counting", "outcomes": [first, second]})
    assert summary["tokens"] == {"input_tokens": 400, "output_tokens": 40}
    assert "| counting | 400 | 0 | 0 | 40 |" in report([{"model": "counting", "outcomes": [first, second]}])
