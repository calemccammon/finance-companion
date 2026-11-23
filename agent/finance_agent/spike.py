"""Spike for issue #3: a fixed surface standing in for the agent's answer."""

CATALOG_ID = "https://github.com/calemccammon/finance-companion/catalog/v1"
_closes = iter([183.02, 184.55, 181.90])


def surface_for(question: str) -> list[dict]:
    return [
        {"version": "v0.9.1", "createSurface": {"surfaceId": "s1", "catalogId": CATALOG_ID}},
        {
            "version": "v0.9.1",
            "updateComponents": {
                "surfaceId": "s1",
                "components": [
                    {"id": "root", "component": "Column", "children": ["title", "close", "refresh"]},
                    {"id": "title", "component": "Text", "text": question, "variant": "h3"},
                    {"id": "close", "component": "MetricCard", "label": "Close", "value": {"path": "/close"}},
                    {"id": "refresh_label", "component": "Text", "text": "Refresh"},
                    {
                        "id": "refresh",
                        "component": "Button",
                        "child": "refresh_label",
                        "action": {"event": {"name": "refresh", "context": {"ticker": "AAPL"}}},
                    },
                ],
            },
        },
        {"version": "v0.9.1", "updateDataModel": {"surfaceId": "s1", "path": "/close", "value": 182.31}},
    ]


def refreshed_close() -> list[dict]:
    return [{"version": "v0.9.1", "updateDataModel": {"surfaceId": "s1", "path": "/close", "value": next(_closes)}}]
