"""A JSON Schema for one answer's layout, for a model that can be held to a schema.

The schema describes exactly one `updateComponents` message for one surface,
built from the app's catalog. A model whose output must follow it cannot write
broken JSON, nest a component inside another's `children`, add fields a
component does not have, or write a figure or a list where a binding is
expected.

Given the surface's data, the schema also lists the paths a binding may name:
lists for charts and rankings, numbers for a MetricCard's value, strings for
text. A component that needs a kind of path the data does not have is left
out, so a question answered without data can only be answered in words. The
template form of a component's children is left out too, since its paths are
read from each item and cannot be listed in advance; RankedBars draws lists.

The agent's own checks still run on what comes back: the schema cannot know
whether every component is reachable from the root.
"""

import copy
import json
from functools import cache

from a2ui.core.schema import ProtocolVersion
from a2ui.core.schema.common_types_schema import get_common_types_schema_json

from finance_agent.catalog import CATALOG_PATH, data_properties

COMMON = "common_types.json#/$defs/"


# The kinds of binding, each a copy of DataBinding until the data narrows it.
LIST, NUMBER, STRING = "ListBinding", "NumberBinding", "StringBinding"


def layout_schema(surface_id: str, version: str, data: dict | None = None) -> dict:
    """The schema of one `updateComponents` message for [surface_id]. With [data], each
    binding must name a path in it, of the kind the property draws."""
    components, defs = copy.deepcopy(_parts())
    if data is not None:
        components, defs = _bound_to(data, components, defs)
    return {
        "type": "object",
        "properties": {
            "version": {"const": version},
            "updateComponents": {
                "type": "object",
                "properties": {
                    "surfaceId": {"const": surface_id},
                    "components": {"type": "array", "minItems": 1, "items": {"anyOf": components}},
                },
                "required": ["surfaceId", "components"],
                "additionalProperties": False,
            },
        },
        "required": ["version", "updateComponents"],
        "additionalProperties": False,
        "$defs": defs,
    }


@cache
def _parts() -> tuple[list[dict], dict]:
    """Each component's schema, and the shared definitions they use."""
    catalog = json.loads(CATALOG_PATH.read_text())
    common = json.loads(get_common_types_schema_json(ProtocolVersion.V0_9_1))["$defs"]
    # Every component may carry the common envelope, and a weight in a Row or Column: the
    # basic components declare it, the app's own draw with it, and the SDK accepts it on all.
    envelope = {
        **common["ComponentCommon"]["properties"],
        "weight": catalog["components"]["Text"]["properties"]["weight"],
    }

    components = []
    for name, schema in catalog["components"].items():
        schema = _local_refs(copy.deepcopy(schema))
        for prop in data_properties()[name]:
            schema["properties"][prop] = {"$ref": f"#/$defs/{LIST}"}
        schema["properties"] = {**_local_refs(copy.deepcopy(envelope)), **schema["properties"]}
        schema["required"] = ["id", *schema.get("required", [])]
        schema["additionalProperties"] = False
        schema.pop("description", None)
        components.append(schema)

    defs = {name: _without_function_calls(d) for name, d in common.items()}
    # A number on screen always comes from the data: bound, never written.
    defs["DynamicNumber"] = {"$ref": f"#/$defs/{NUMBER}"}
    defs["DynamicString"]["oneOf"] = [{"type": "string"}, {"$ref": f"#/$defs/{STRING}"}]
    for kind in (LIST, NUMBER, STRING):
        defs[kind] = copy.deepcopy(defs["DataBinding"])
    return components, _reachable(components, defs)


def _bound_to(data: dict, components: list[dict], defs: dict) -> tuple[list[dict], dict]:
    """[components] and [defs] with every binding limited to the paths in [data]."""
    paths = {LIST: [], NUMBER: [], STRING: []}
    for path, value in _paths(data):
        if isinstance(value, list):
            paths[LIST].append(path)
        elif isinstance(value, int | float) and not isinstance(value, bool):
            paths[NUMBER].append(path)
        elif isinstance(value, str):
            paths[STRING].append(path)
    paths["DataBinding"] = [p for kind in (LIST, NUMBER, STRING) for p in paths[kind]]
    for kind, found in paths.items():
        defs[kind] = _binding(found) if found else None
    if "ChildList" in defs:
        defs["ChildList"]["oneOf"] = [c for c in defs["ChildList"]["oneOf"] if c.get("type") == "array"]

    # A definition that has lost every choice is gone too, and so is whatever needs it.
    while empty := {name for name, d in defs.items() if d is None}:
        defs = {name: _without(d, empty) for name, d in defs.items() if d is not None}
        components = [c for c in (_without(c, empty) for c in components) if c is not None]
    return components, _reachable(components, defs)


def _binding(paths: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {"path": {"enum": paths}},
        "required": ["path"],
        "additionalProperties": False,
    }


# A list longer than this is drawn whole, never item by item (a price history's points).
LONGEST_INDEXED_LIST = 25


def _paths(node, prefix: str = ""):
    """Every path in [node], with the value there."""
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list) and len(node) <= LONGEST_INDEXED_LIST:
        items = enumerate(node)
    else:
        return
    for key, value in items:
        path = f"{prefix}/{str(key).replace('~', '~0').replace('/', '~1')}"
        yield path, value
        yield from _paths(value, path)


def _without(node, empty: set[str]):
    """[node] without what refers to an [empty] definition; None if it cannot do without."""
    if isinstance(node, list):
        return [n for n in (_without(n, empty) for n in node) if n is not None]
    if not isinstance(node, dict):
        return node
    if node.get("$ref", "").removeprefix("#/$defs/") in empty:
        return None
    out = {}
    for key, value in node.items():
        if key == "properties":
            kept = {k: _without(v, empty) for k, v in value.items()}
            if any(kept[k] is None for k in node.get("required", [])):
                return None
            out[key] = {k: v for k, v in kept.items() if v is not None}
        elif key in ("oneOf", "anyOf"):
            choices = _without(value, empty)
            if not choices:
                return None
            out[key] = choices
        else:
            kept = _without(value, empty)
            if kept is None:
                return None
            out[key] = kept
    return out


def _local_refs(node):
    """Points the catalog's references to the shared definitions at this schema's own `$defs`."""
    if isinstance(node, dict):
        return {
            k: ("#/$defs/" + v[len(COMMON) :] if k == "$ref" and v.startswith(COMMON) else _local_refs(v))
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [_local_refs(n) for n in node]
    return node


def _without_function_calls(node):
    """Drops every choice that is a function call: the app's catalog has no functions."""
    if isinstance(node, dict):
        node = {k: _without_function_calls(v) for k, v in node.items()}
        for key in ("oneOf", "anyOf"):
            if key in node:
                node[key] = [choice for choice in node[key] if "FunctionCall" not in json.dumps(choice)]
        return node
    if isinstance(node, list):
        return [_without_function_calls(n) for n in node]
    return node


def _reachable(components: list[dict], defs: dict) -> dict:
    """The definitions the components use, directly or through other definitions."""
    found: dict = {}
    pending = [components]
    while pending:
        for name in _refs(pending.pop()):
            if name not in found:
                found[name] = defs[name]
                pending.append(defs[name])
    return found


def _refs(node) -> set[str]:
    if isinstance(node, dict):
        names = {node["$ref"].removeprefix("#/$defs/")} if isinstance(node.get("$ref"), str) else set()
        return names.union(*(_refs(v) for v in node.values()))
    if isinstance(node, list):
        return set().union(*(_refs(n) for n in node))
    return set()
