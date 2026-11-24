"""Scores how well a model answers within the app's rules.

Each question in questions.json is put to the agent with the chosen model.
What happens is recorded through the agent's observer and scored:

- renders:        the final layout passed every check (not the fallback)
- shows_data:     it rendered, and for a question that needs data, the screen binds at
                  least one figure, chart or ranking to it (a heading alone does not count)
- first_try:      the first layout passed every check, with no correction
- catalog_only:   no layout used a component the app does not have
- bindings:       no layout bound to a path missing from the data
- no_written_figure: no layout wrote a figure itself
- right_tools:    the tools called include every tool the question needs, and
                  questions that need none (off-topic, unanswerable) called none

    uv run python evals/run.py --out evals/results/qwen3-8b-schema.json
    uv run python evals/run.py --no-schema --out evals/results/qwen3-8b.json
    uv run python evals/run.py --report evals/results/*.json > evals/REPORT.md
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from finance_agent.agent import Agent
from finance_agent.catalog import load_catalog
from finance_agent.model import ModelClient, client_from_env
from finance_agent.warehouse import Warehouse

QUESTIONS = Path(__file__).with_name("questions.json")
SCORES = ("renders", "shows_data", "first_try", "catalog_only", "bindings", "no_written_figure", "right_tools")


def failure_class(reasons: str) -> list[str]:
    """Sorts a rejection's reasons into the classes the report counts."""
    found = []
    if "is not JSON" in reasons:
        found.append("not JSON")
    if any(
        k in reasons
        for k in ("Missing root component", "missing an 'id'", "missing required 'id'", "not reachable from")
    ):
        found.append("broken component tree")
    if ".children: [{" in reasons:
        found.append("components nested in children")
    if re.search(r": '/[^']*' is not valid under any of the given schemas", reasons):
        found.append("path written as plain text")
    if "Extra inputs are not permitted" in reasons:
        found.append("stray fields")
    if "Unrecognized component" in reasons or "not found in catalog" in reasons:
        found.append("unknown component")
    if "which is not in the data" in reasons or "not a list in the data" in reasons:
        found.append("missing data path")
    if "writes the number" in reasons or "writes the figure" in reasons:
        found.append("written figure")
    if "exactly one updateComponents" in reasons:
        found.append("no layout")
    if "called a tool instead" in reasons:
        found.append("tool call in place of a layout")
    return found or ["other schema error"]


@dataclass
class Outcome:
    id: str
    tools: list[str] = field(default_factory=list)
    tool_errors: int = 0
    rejections: list[list[str]] = field(default_factory=list)
    # Each rejection's reasons as the checks wrote them, to sort again without a rerun.
    reasons: list[str] = field(default_factory=list)
    fallback: bool = False
    accepted: bool = False
    error: str | None = None
    seconds: float = 0.0
    scores: dict[str, bool] = field(default_factory=dict)
    # The components of the layout that passed, to see what the screen held.
    layout: list[dict] | None = None


def run_question(
    question: dict, model: ModelClient, warehouse: Warehouse, catalog, use_schema: bool | None = None
) -> Outcome:
    outcome = Outcome(id=question["id"])

    def observe(kind: str, detail: dict) -> None:
        if kind == "tool":
            outcome.tools.append(detail["name"])
            outcome.tool_errors += detail["error"] is not None
        elif kind == "rejected":
            outcome.rejections.append(failure_class(detail["reasons"]))
            outcome.reasons.append(detail["reasons"])
        elif kind == "fallback":
            outcome.fallback = True
        elif kind == "accepted":
            outcome.accepted = True
            outcome.layout = detail["components"]

    agent = Agent(warehouse, catalog, model, observer=observe, use_schema=use_schema)
    started = time.monotonic()
    try:
        list(agent.answer(question["ask"]))
    except Exception as e:
        outcome.error = f"{type(e).__name__}: {e}"
    outcome.seconds = round(time.monotonic() - started, 2)
    outcome.scores = score(question, outcome)
    return outcome


def score(question: dict, outcome: Outcome) -> dict[str, bool]:
    every = [c for attempt in outcome.rejections for c in attempt]
    needed = set(question["tools"])
    called = set(outcome.tools)
    right_tools = needed <= called if needed else not called
    renders = outcome.accepted and not outcome.fallback and outcome.error is None
    return {
        "renders": renders,
        "shows_data": renders and (not needed or _binds(outcome.layout)),
        "first_try": outcome.accepted and not outcome.rejections and outcome.error is None,
        "catalog_only": "unknown component" not in every,
        "bindings": "missing data path" not in every,
        "no_written_figure": "written figure" not in every,
        "right_tools": right_tools,
    }


def _binds(node) -> bool:
    """Whether anything in [node] is bound to the data: a `{"path": ...}`, or a list template."""
    if isinstance(node, dict):
        return "path" in node or any(_binds(v) for v in node.values())
    if isinstance(node, list):
        return any(_binds(v) for v in node)
    return False


def run(model: ModelClient, questions: list[dict], use_schema: bool | None = None) -> dict:
    warehouse, catalog = Warehouse(), load_catalog()
    outcomes = []
    for q in questions:
        outcome = run_question(q, model, warehouse, catalog, use_schema)
        outcomes.append(outcome)
        print(f"{q['id']:>20}  {' '.join(k for k, v in outcome.scores.items() if not v) or 'ok'}", file=sys.stderr)
    schema = Agent(warehouse, catalog, model, use_schema=use_schema).use_schema
    return {
        "model": model.name + (", layouts held to a schema" if schema else ""),
        "outcomes": [asdict(o) for o in outcomes],
    }


def attempts(outcome: dict) -> list[list[str]]:
    """Each rejected attempt's classes, sorted from its reasons by today's rules when the
    results kept them, so a new class needs no rerun."""
    if outcome.get("reasons"):
        return [failure_class(r) for r in outcome["reasons"]]
    return outcome["rejections"]


def summarise(result: dict) -> dict:
    outcomes = result["outcomes"]
    n = len(outcomes)
    rates = {s: sum(o["scores"][s] for o in outcomes) for s in SCORES}
    rejected = [a for o in outcomes for a in attempts(o)]
    classes = Counter(c for a in rejected for c in a)
    accepted = sum(o["accepted"] for o in outcomes)
    # The app's own checks (bindings, written figures) run only on an answer the SDK has
    # accepted: one that rendered, or one those checks rejected.
    own = {"missing data path", "written figure"}
    return {
        "model": result["model"],
        "questions": n,
        "passed": rates,
        "failure_classes": dict(classes),
        "attempts": accepted + len(rejected),
        "reached_own_checks": accepted + sum(bool(own & set(a)) for a in rejected),
    }


def report(results: list[dict]) -> str:
    lines = [
        "# Evaluation results",
        "",
        "Each model answered the same questions through the real agent, tools and checks. "
        "A score is the number of questions, out of the total, that met it.",
        "",
        "| Model | Questions | " + " | ".join(SCORES) + " |",
        "|---|---|" + "---|" * len(SCORES),
    ]
    summaries = [summarise(r) for r in results]
    for s in summaries:
        lines.append(f"| {s['model']} | {s['questions']} | " + " | ".join(str(s["passed"][k]) for k in SCORES) + " |")
    lines += [
        "",
        "## How far answers got",
        "",
        "The catalog_only, bindings and no_written_figure scores count questions where no attempt broke "
        "that rule. The app's checks for bindings and written figures run only on an answer the A2UI SDK "
        "has accepted, so they say little when few answers got that far.",
        "",
        "| Model | Attempts | Reached the app's own checks |",
        "|---|---|---|",
    ]
    for s in summaries:
        lines.append(f"| {s['model']} | {s['attempts']} | {s['reached_own_checks']} |")
    lines += ["", "## Why layouts were rejected", "", "| Model | Class | Count |", "|---|---|---|"]
    for s in summaries:
        for cls, count in sorted(s["failure_classes"].items(), key=lambda kv: -kv[1]):
            lines.append(f"| {s['model']} | {cls} | {count} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="Write the run's results here as JSON.")
    parser.add_argument("--only", nargs="*", help="Question ids to run; all by default.")
    parser.add_argument(
        "--no-schema", action="store_true", help="Let the model write layouts freely, even if it can follow a schema."
    )
    parser.add_argument("--report", nargs="*", type=Path, help="Print a Markdown report of these result files.")
    args = parser.parse_args()

    if args.report:
        print(report([json.loads(p.read_text()) for p in args.report]), end="")
        return
    questions = json.loads(QUESTIONS.read_text())
    if args.only:
        questions = [q for q in questions if q["id"] in set(args.only)]
    result = run(client_from_env(), questions, use_schema=False if args.no_schema else None)
    text = json.dumps(result, indent=1)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
    print(json.dumps(summarise(result), indent=1))


if __name__ == "__main__":
    main()
