"""The component catalog the app renders, as the agent sees it."""

import json
from functools import cache
from pathlib import Path

from a2ui.core.catalog import Catalog

# Written by the app's CatalogSchemaTest from the components it registers, so
# the agent never offers a component the app cannot draw.
CATALOG_PATH = Path(__file__).resolve().parents[2] / "catalog" / "finance-catalog.json"


def load_catalog():
    """The app's catalog, for validating surfaces before they are sent."""
    return Catalog.from_json(json.loads(CATALOG_PATH.read_text()), protocol_version="0.9.1")


@cache
def data_properties() -> dict[str, frozenset[str]]:
    """For each component, the properties that hold a list from the data (a chart's points,
    a ranking's rows): those the catalog types as a DynamicValue. They must be bound."""
    components = json.loads(CATALOG_PATH.read_text())["components"]
    return {
        name: frozenset(
            prop
            for prop, prop_schema in schema["properties"].items()
            if prop_schema.get("$ref", "").endswith("/DynamicValue")
        )
        for name, schema in components.items()
    }
