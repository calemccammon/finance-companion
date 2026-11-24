"""Checks every surface the model lays out, before anything is sent.

The SDK checks a surface against the catalog: known components, required
properties, the right types. Three rules of this app it cannot know:

- Every binding must name a path that exists in the data model. A binding to
  nothing draws an empty card, which looks like a missing figure.
- A chart's points and a ranking's rows must be bound to a list in the data.
  The catalog's type for them also takes a string, which draws nothing.
- The model must not write figures itself. Every figure on screen comes from
  the warehouse through the data model; a figure typed by the model may be
  wrong, out of date, or made up.
"""

import json
import re
from collections.abc import Iterator
from typing import Any

from finance_agent.catalog import data_properties

# Properties that take a literal number by design: layout, not data.
LITERAL_NUMBER_PROPERTIES = frozenset({"weight"})

_NUMBER = re.compile(r"(?P<dollar>\$)?\s?(?P<number>-?\d[\d,]*(?:\.\d+)?)\s?(?P<percent>%)?")


class SurfaceRejected(ValueError):
    """The surface breaks a rule. The message is written for the model, to correct it."""


def check_surface(components: list[dict], data: dict) -> None:
    """Raises SurfaceRejected naming every problem found, or returns if there is none."""
    problems = (
        list(_bindings(components, data)) + list(_unbound_data(components)) + list(_written_figures(components, data))
    )
    if problems:
        raise SurfaceRejected("; ".join(problems))


def resolve(data: Any, pointer: str) -> tuple[bool, Any]:
    """Looks up a JSON Pointer in [data]. Returns whether it exists, and the value."""
    node = data
    for raw in pointer.strip("/").split("/") if pointer.strip("/") else []:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and key.isdigit() and int(key) < len(node):
            node = node[int(key)]
        else:
            return False, None
    return True, node


def _bindings(components: list[dict], data: dict) -> Iterator[str]:
    by_id = {c.get("id"): c for c in components}
    # A List's template is drawn once per item, and paths inside it without a
    # leading slash are read from the item: check them against the first one.
    scopes: dict[str, Any] = {}
    for c in components:
        for value in c.values():
            if isinstance(value, dict) and {"componentId", "path"} <= value.keys():
                found, items = resolve(data, value["path"])
                if not found or not isinstance(items, list):
                    yield f"component {c.get('id')!r} repeats over {value['path']!r}, which is not a list in the data"
                    continue
                for member in _subtree(value["componentId"], by_id):
                    scopes[member] = items[0] if items else {}

    for c in components:
        for prop, path in _paths(c):
            scope = scopes.get(c.get("id"))
            if path.startswith("/") or scope is None:
                found, _ = resolve(data, path)
            else:
                found, _ = resolve(scope, path)
            if not found:
                yield f"component {c.get('id')!r} binds {prop} to {path!r}, which is not in the data"


def _unbound_data(components: list[dict]) -> Iterator[str]:
    for c in components:
        for prop in data_properties().get(c.get("component"), ()):
            value = c.get(prop)
            if prop in c and not (isinstance(value, dict) and set(value) == {"path"}):
                yield (
                    f"component {c.get('id')!r} writes its {prop} as {json.dumps(value)[:60]}; "
                    f'bind it to a list in the data, such as {{"path": "/r1/rows"}}'
                )


def _paths(component: dict) -> Iterator[tuple[str, str]]:
    for prop, value in component.items():
        if isinstance(value, dict) and set(value) == {"path"} and isinstance(value["path"], str):
            yield prop, value["path"]


def _subtree(root: str, by_id: dict[str, dict]) -> Iterator[str]:
    seen, stack = set(), [root]
    while stack:
        cid = stack.pop()
        if cid in seen or cid not in by_id:
            continue
        seen.add(cid)
        yield cid
        for value in by_id[cid].values():
            if isinstance(value, str) and value in by_id:
                stack.append(value)
            elif isinstance(value, list):
                stack += [v for v in value if isinstance(v, str)]
            elif isinstance(value, dict) and "componentId" in value:
                stack.append(value["componentId"])


def _numbers(node: Any) -> Iterator[float]:
    if isinstance(node, bool):
        return
    if isinstance(node, int | float):
        yield float(node)
    elif isinstance(node, dict):
        for v in node.values():
            yield from _numbers(v)
    elif isinstance(node, list):
        for v in node:
            yield from _numbers(v)


def _written_figures(components: list[dict], data: dict) -> Iterator[str]:
    figures = {text for v in _numbers(data) for text in (f"{v:.2f}", f"{v:.1f}", f"{abs(v):.2f}", f"{abs(v):.1f}")}
    for c in components:
        cid = c.get("id")
        for prop, value in c.items():
            if isinstance(value, bool) or prop in LITERAL_NUMBER_PROPERTIES:
                continue
            if isinstance(value, int | float):
                yield f"component {cid!r} writes the number {value} in {prop}; bind it to a path in the data instead"
            elif isinstance(value, str) and prop not in {"id", "component"}:
                for match in _NUMBER.finditer(value):
                    number = match["number"].replace(",", "")
                    money_or_share = match["dollar"] or match["percent"]
                    if money_or_share or ("." in number and number.lstrip("-") in figures):
                        yield (
                            f"component {cid!r} writes the figure {match.group(0).strip()!r} in its {prop}; "
                            "show figures with MetricCard or a chart bound to the data, never in text"
                        )
