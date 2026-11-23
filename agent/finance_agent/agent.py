"""From a question to a surface.

1. The model is given the question and the analysis tools.
2. It calls tools; the server runs them against the warehouse and stores each
   result in the surface's data model at `/r1`, `/r2`, ... The model is told
   where each result went and what it holds.
3. The model answers with one `updateComponents` message: a layout whose
   figures bind to those paths.
4. The layout is checked (catalog, bindings, no written figures). A rejected
   layout goes back to the model once, with the reasons; a second rejection
   is answered with a plain message instead.

The server sends `createSurface` and `updateDataModel` itself, so the model
never handles the data, only where it is.
"""

import itertools
import json
import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import timedelta

from a2ui.core.exceptions import A2uiError
from a2ui.core.schema.v0_9.client_capabilities import A2uiClientCapabilities, V09Capabilities
from a2ui.inference_formats.direct_json import DirectJsonFormatFactory
from a2ui.parser.response_part import A2uiPart
from a2ui.processor.catalog_config import CatalogConfig
from a2ui.processor.generator import A2uiGenerator

from finance_agent.checks import SurfaceRejected, check_surface
from finance_agent.model import ModelClient, ModelTurn, ToolTurn, Turn, UserTurn
from finance_agent.tools import TOOLS, ToolError, run_tool, tool_declarations
from finance_agent.warehouse import Warehouse

log = logging.getLogger(__name__)

VERSION = "v0.9.1"
MAX_TOOL_ROUNDS = 4
MAX_CORRECTIONS = 1

RULES = """\
You answer questions about ten US stocks ({tickers}) and US economic series, with one
screen of components that the app draws. The data covers {first} to {last}.

How to answer:
1. Call tools to get the data you need. Do not answer from memory.
2. Each tool result is stored in the screen's data model at the path you are told, such
   as /r1. Bind every figure to a path in it, for example {{"path": "/r1/latest/close"}}.
3. Never write a number yourself: not in a component property, not in text. Words such as
   "rose", "fell" or "most volatile" are fine; the figures come from the bindings.
4. Answer with exactly one A2UI JSON block holding one updateComponents message for surface
   "{surface}". The createSurface message and the data are sent for you; do not send them.
5. Keep it to one screen: a heading, one to four MetricCards, and at most one chart or ranking.
6. On RankedBars, set rowAction to "open_ticker" so a row can be pressed to ask about it.
7. Under a PriceChart or OverlayChart from result /rN you may add a Row of Buttons with
   actions {{"event": {{"name": "set_range", "context": {{"result": "/rN", "days": 30}}}}}}, and
   the same with 90 and 180 days, labelled "1 month", "3 months" and "6 months".
8. Do not state a result's date range in text: the range buttons change it, and text would
   not follow. Bind a MetricCard's caption to the result's "start" or "end" instead.
9. If the question is not about these stocks or the economy, answer with a short Text saying
   what you can help with.

"""

FALLBACK_TEXT = "I could not lay out an answer to that. Try asking another way."


@dataclass
class Surface:
    id: str
    question: str
    data: dict = field(default_factory=dict)
    # Which tool and arguments made each result, so an action can run it again.
    results: dict[str, tuple[str, dict]] = field(default_factory=dict)
    transcript: list[Turn] = field(default_factory=list)
    components: list[dict] = field(default_factory=list)
    corrections_left: int = MAX_CORRECTIONS


class Agent:
    def __init__(
        self,
        warehouse: Warehouse,
        catalog,
        model: ModelClient,
        observer: Callable[[str, dict], None] | None = None,
    ):
        """[observer], if given, hears what happens while answering: tool calls,
        rejected layouts and fallbacks. The evaluations score a model from it."""
        self.observer = observer or (lambda kind, detail: None)
        self.warehouse = warehouse
        self.catalog = catalog
        self.model = model
        generator = A2uiGenerator([CatalogConfig(catalog=catalog)], inference_format_factory=DirectJsonFormatFactory())
        capabilities = A2uiClientCapabilities(v0_9=V09Capabilities(supported_catalog_ids=[catalog.catalog_id]))
        self._processor = generator.create_processor(capabilities)
        self._surfaces: dict[str, Surface] = {}
        self._ids = itertools.count(1)
        self._tools = tool_declarations()

    def surface(self, surface_id: str) -> Surface | None:
        """What the agent holds for a surface it has sent."""
        return self._surfaces.get(surface_id)

    # --- answering --------------------------------------------------------

    def answer(self, question: str) -> Iterator[dict]:
        """The A2UI messages that answer [question] on a new surface, in order.

        The first item is `{"question": ...}`, not an A2UI message: it names the
        question being answered, which the app does not know when a tap asked it.
        """
        yield {"question": question}
        surface = Surface(id=f"answer-{next(self._ids)}", question=question)
        self._surfaces[surface.id] = surface
        surface.transcript.append(UserTurn(question))
        yield self._message("createSurface", {"surfaceId": surface.id, "catalogId": self.catalog.catalog_id})

        reply = self._gather(surface)
        components = self._lay_out(surface, reply)
        surface.components = components
        yield self._message("updateDataModel", {"surfaceId": surface.id, "path": "/", "value": surface.data})
        yield self._message("updateComponents", {"surfaceId": surface.id, "components": components})

    def _gather(self, surface: Surface) -> ModelTurn:
        """Lets the model call tools until it answers. Returns its answering turn."""
        for _ in range(MAX_TOOL_ROUNDS):
            reply = self._ask(surface)
            surface.transcript.append(reply)
            if not reply.tool_calls:
                return reply
            for call in reply.tool_calls:
                surface.transcript.append(ToolTurn(call, self._run(surface, call.name, call.arguments)))
        reply = self._ask(surface, extra="Answer now with the results you have; do not call more tools.")
        surface.transcript.append(reply)
        return reply

    def _run(self, surface: Surface, name: str, arguments: dict) -> dict:
        try:
            result = run_tool(self.warehouse, name, arguments)
        except ToolError as e:
            self.observer("tool", {"name": name, "arguments": arguments, "error": str(e)})
            return {"error": str(e)}
        self.observer("tool", {"name": name, "arguments": arguments, "error": None})
        path = f"/r{len(surface.results) + 1}"
        surface.data[path[1:]] = result.data
        surface.results[path] = (name, arguments)
        return {"storedAt": path, "data": _preview(result.data)}

    def _lay_out(self, surface: Surface, reply: ModelTurn) -> list[dict]:
        """The components of the model's answer, checked; corrected once if need be."""
        while True:
            try:
                components = self._components(surface, reply)
                self.observer("accepted", {"components": components})
                return components
            except SurfaceRejected as e:
                log.info("surface %s rejected: %s", surface.id, e)
                self.observer("rejected", {"reasons": str(e)})
                if surface.corrections_left <= 0:
                    self.observer("fallback", {})
                    return _fallback()
                surface.corrections_left -= 1
                reply = self._ask(surface, extra=f"Your screen was rejected: {e}. Send a corrected updateComponents.")
                surface.transcript.append(reply)

    def _components(self, surface: Surface, reply: ModelTurn) -> list[dict]:
        if reply.tool_calls:
            raise SurfaceRejected("you called a tool instead of answering")
        state = self._processor.create_state()
        state.apply(
            [
                self._message("createSurface", {"surfaceId": surface.id, "catalogId": self.catalog.catalog_id}),
                self._message("updateDataModel", {"surfaceId": surface.id, "path": "/", "value": surface.data}),
            ]
        )
        try:
            parts = self._processor.parse_response(reply.text, state=state)
        except A2uiError as e:
            # Unknown components, bad properties, a surface that does not exist.
            raise SurfaceRejected(str(e)) from e
        updates = [
            m
            for part in parts
            if isinstance(part, A2uiPart)
            for m in (x.model_dump(by_alias=True, exclude_none=True, mode="json") for x in part.a2ui)
            if "updateComponents" in m
        ]
        if len(updates) != 1:
            raise SurfaceRejected(f"answer with exactly one updateComponents message for surface {surface.id!r}")
        components = updates[0]["updateComponents"]["components"]
        check_surface(components, surface.data)
        return components

    def _ask(self, surface: Surface, extra: str | None = None) -> ModelTurn:
        if extra:
            surface.transcript.append(UserTurn(extra))
        return self.model.reply(self._system(surface), surface.transcript, self._tools)

    def _system(self, surface: Surface) -> str:
        rules = RULES.format(
            tickers=", ".join(sorted(self.warehouse.tickers)),
            first=self.warehouse.first_date,
            last=self.warehouse.last_date,
            surface=surface.id,
        )
        return rules + self._processor.prompt_snippet

    # --- actions and errors from the app ------------------------------------

    def act(self, message: dict) -> Iterator[dict]:
        """Answers an A2UI client message: an `action` from a tap, or an `error` from the renderer."""
        if "error" in message:
            yield from self._correct(message["error"])
            return
        action = message.get("action", {})
        context = action.get("context") or {}
        surface = self._surfaces.get(action.get("surfaceId", ""))
        match action.get("name"):
            case "set_range" if surface is not None:
                yield from self._set_range(surface, context)
            case "open_ticker" if isinstance(context.get("ticker"), str):
                yield from self.answer(f"How is {context['ticker']} doing?")
            case other:
                log.info("ignored action %r", other)

    def _set_range(self, surface: Surface, context: dict) -> Iterator[dict]:
        """Runs a result's tool again over the last [days] days. No model call: only the data changes."""
        path, days = context.get("result"), context.get("days")
        if path not in surface.results or not isinstance(days, int) or not 1 <= days <= 366:
            log.info("set_range with a bad context %r", context)
            return
        name, arguments = surface.results[path]
        if "start" not in TOOLS[name].args.model_fields:
            return
        end = self.warehouse.last_date
        arguments = {**arguments, "start": (end - timedelta(days=days)).isoformat(), "end": end.isoformat()}
        result = run_tool(self.warehouse, name, arguments)
        surface.data[path[1:]] = result.data
        surface.results[path] = (name, arguments)
        yield self._message("updateDataModel", {"surfaceId": surface.id, "path": path, "value": result.data})

    def _correct(self, error: dict) -> Iterator[dict]:
        surface = self._surfaces.get(error.get("surfaceId", ""))
        log.info("renderer reported %s", error)
        if surface is None or surface.corrections_left <= 0:
            return
        surface.corrections_left -= 1
        reply = self._ask(
            surface,
            extra=f"The app could not draw your screen: {error.get('message')}. Send a corrected updateComponents.",
        )
        surface.transcript.append(reply)
        try:
            components = self._components(surface, reply)
        except SurfaceRejected:
            components = _fallback()
        surface.components = components
        yield self._message("updateComponents", {"surfaceId": surface.id, "components": components})

    @staticmethod
    def _message(kind: str, body: dict) -> dict:
        return {"version": VERSION, kind: body}


def _preview(data: dict) -> dict:
    """A tool result as the model sees it: long lists are cut to their first rows and a count."""

    def cut(node):
        if isinstance(node, list) and len(node) > 5:
            return {"rows": len(node), "first": [cut(n) for n in node[:3]], "last": cut(node[-1])}
        if isinstance(node, dict):
            return {k: cut(v) for k, v in node.items()}
        if isinstance(node, list):
            return [cut(n) for n in node]
        return node

    return json.loads(json.dumps(cut(data)))


def _fallback() -> list[dict]:
    return [{"id": "root", "component": "Text", "text": FALLBACK_TEXT}]
