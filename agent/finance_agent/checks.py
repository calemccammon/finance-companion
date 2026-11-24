"""Checks every surface the model lays out, before anything is sent.

The SDK checks a surface against the catalog: known components, required
properties, the right types. Six rules of this app it cannot know:

- Every binding must name a path that exists in the data model. A binding to
  nothing draws an empty card, which looks like a missing figure.
- A chart's points and a ranking's rows must be bound to a list in the data.
  The catalog's type for them also takes a string, which draws nothing.
- The model must not write figures itself. Every figure on screen comes from
  the warehouse through the data model; a figure typed by the model may be
  wrong, out of date, or made up.
- A path belongs in a binding, never in text. Written into a string it is
  drawn as it is, such as "Apple closed at $/r1/latest/close".
- A MetricCard showing one row of a list must name that row in its label.
  Rankings are sorted by their figure, so the first row is not the first
  stock asked about; a label guessed from the question can be wrong.
- A figure must be drawn in its format: a price as currency, a change as a
  change, a rate as a percent. A closing price drawn as a change would read
  "+342.56%".
"""

import json
import re
from collections.abc import Iterator
from typing import Any

from finance_agent.catalog import data_properties
from finance_agent.tools import figure_format

# Properties that take a literal number by design: layout, not data.
LITERAL_NUMBER_PROPERTIES = frozenset({"weight"})

# A data path, or a placeholder for one, written into a string.
_WRITTEN_PATH = re.compile(r"/r\d+(?:/[\w~]+)*|\$\{[^}]*\}|\{\{[^}]*\}\}")
# A path into one row of a list: the list's path, the row's index.
_ROW = re.compile(r"^(?P<list>/r\d+(?:/[\w~]+)*?)/(?P<index>\d+)(?:/|$)")

_NUMBER = re.compile(r"(?P<dollar>\$)?\s?(?P<number>-?\d[\d,]*(?:\.\d+)?)\s?(?P<percent>%)?")


class SurfaceRejected(ValueError):
    """The surface breaks a rule. The message is written for the model, to correct it."""


def check_surface(components: list[dict], data: dict) -> None:
    """Raises SurfaceRejected naming every problem found, or returns if there is none."""
    problems = [
        *_bindings(components, data),
        *_unbound_data(components),
        *_written_figures(components, data),
        *_written_paths(components),
        *_unnamed_rows(components, data),
        *_wrong_formats(components, data),
    ]
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


def _written_paths(components: list[dict]) -> Iterator[str]:
    for c in components:
        for prop, value in c.items():
            if isinstance(value, str) and prop not in {"id", "component"} and (match := _WRITTEN_PATH.search(value)):
                yield (
                    f"component {c.get('id')!r} writes {match.group(0)!r} into its {prop}, where it is shown as it "
                    'is; bind the property to the data instead, such as {"path": "/r1/latest/close"}'
                )


def _unnamed_rows(components: list[dict], data: dict) -> Iterator[str]:
    for c in components:
        value, label = c.get("value"), c.get("label")
        if c.get("component") != "MetricCard" or not isinstance(value, dict):
            continue
        row_path = _ROW.match(str(value.get("path", "")))
        if row_path is None:
            continue
        found, row = resolve(data, f"{row_path['list']}/{row_path['index']}")
        if not found or not isinstance(row, dict):
            continue
        names = [str(row[k]) for k in ("ticker", "name") if isinstance(row.get(k), str)]
        if not names:
            continue
        here = f"{row_path['list']}/{row_path['index']}/"
        if isinstance(label, dict) and str(label.get("path", "")).startswith(here):
            continue
        if isinstance(label, str) and any(re.search(rf"\b{re.escape(n)}\b", label, re.I) for n in names):
            continue
        yield (
            f"component {c.get('id')!r} shows row {row_path['index']} of {row_path['list']}, which is "
            f"{' / '.join(names)}, but its label does not say so; name that row in the label, or bind the label "
            f'to {{"path": "{here}name"}}'
        )


FORMAT_MEANINGS = {
    "currency": "a price in dollars",
    "change": "a change in percent",
    "percent": "a figure in percent",
    "number": "a plain number",
}


def _wrong_formats(components: list[dict], data: dict) -> Iterator[str]:
    for c in components:
        match c.get("component"), c.get("value"), c.get("rows"):
            case "MetricCard", {"path": str(path)}, _:
                shown = path
            case "RankedBars", _, {"path": str(rows)} if isinstance(c.get("valueKey"), str):
                shown = f"{rows}/0/{c['valueKey']}"
            case _:
                continue
        if not resolve(data, shown)[0] or (expected := figure_format(data, shown)) is None:
            continue
        drawn = c.get("format", "number")
        if drawn != expected:
            figure = shown if c.get("component") == "MetricCard" else f"{c['valueKey']} in {rows}"
            yield (
                f"component {c.get('id')!r} draws {figure}, {FORMAT_MEANINGS[expected]}, with format {drawn!r}; "
                f'set "format": "{expected}"'
            )
