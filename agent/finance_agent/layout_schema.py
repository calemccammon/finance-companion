"""A JSON Schema for one answer's layout, for a model that can be held to a schema.

The schema describes exactly one `updateComponents` message for one surface,
built from the app's catalog. A model whose output must follow it cannot write
broken JSON, nest a component inside another's `children`, add fields a
component does not have, or write a figure or a list where a binding is
expected. The
agent's own checks still run on what comes back: the schema cannot know
whether a path exists in the data, or whether every component is reachable
from the root.
"""

import copy
import json
from functools import cache

from a2ui.core.schema import ProtocolVersion
from a2ui.core.schema.common_types_schema import get_common_types_schema_json

from finance_agent.catalog import CATALOG_PATH, data_properties

COMMON = "common_types.json#/$defs/"


def layout_schema(surface_id: str, version: str) -> dict:
    """The schema of one `updateComponents` message for [surface_id]."""
    components, defs = _parts()
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
            schema["properties"][prop] = {"$ref": "#/$defs/DataBinding"}
        schema["properties"] = {**_local_refs(copy.deepcopy(envelope)), **schema["properties"]}
        schema["required"] = ["id", *schema.get("required", [])]
        schema["additionalProperties"] = False
        schema.pop("description", None)
        components.append(schema)

    defs = {name: _without_function_calls(d) for name, d in common.items()}
    # A number on screen always comes from the data: bound, never written.
    defs["DynamicNumber"] = {"$ref": "#/$defs/DataBinding"}
    return components, _reachable(components, defs)


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
