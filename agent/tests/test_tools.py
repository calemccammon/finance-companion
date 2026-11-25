"""The analysis tools against the fixture warehouse.

Expected values are worked out here from the raw mart rows by plain Python,
not by the tools' own SQL, so a mistake in a query shows."""

from datetime import date

import pytest

from finance_agent.tools import (
    FIELD_MEANINGS,
    TOOLS,
    ToolError,
    field_meanings,
    figure_format,
    run_tool,
    tool_declarations,
)
from finance_agent.warehouse import Warehouse


@pytest.fixture(scope="module")
def wh():
    warehouse = Warehouse()
    yield warehouse
    warehouse.close()


def closes(wh, ticker, start, end):
    return [
        r["close_price"]
        for r in wh.rows(
            "SELECT close_price FROM fct_daily_trading "
            "WHERE ticker = ? AND trading_date BETWEEN ? AND ? ORDER BY trading_date",
            [ticker, start, end],
        )
    ]


def test_the_fixture_is_what_the_tests_assume(wh):
    assert len(wh.tickers) == 10
    assert (wh.first_date, wh.last_date) == (date(2026, 5, 19), date(2026, 11, 20))


def test_company_profile(wh):
    data = run_tool(wh, "company_profile", {"ticker": "aapl"}).data
    assert data["ticker"] == "AAPL"
    assert data["company_name"] == "Apple Inc."
    assert data["sector"] == "Technology"


def test_price_history_over_a_range(wh):
    data = run_tool(wh, "price_history", {"ticker": "MSFT", "start": "2026-09-01", "end": "2026-09-30"}).data
    expected = closes(wh, "MSFT", date(2026, 9, 1), date(2026, 9, 30))

    assert [p["close"] for p in data["points"]] == [round(c, 2) for c in expected]
    assert data["latest"]["close"] == round(expected[-1], 2)
    assert data["latest"]["changePct"] == round((expected[-1] / expected[0] - 1) * 100, 2)
    assert data["start"] >= "2026-09-01" and data["end"] <= "2026-09-30"


def test_price_history_defaults_to_the_last_ninety_days(wh):
    data = run_tool(wh, "price_history", {"ticker": "NVDA"}).data
    assert data["end"] == "2026-11-20"
    assert data["start"] >= "2026-08-22"


def test_compare_returns_ranks_best_first(wh):
    data = run_tool(
        wh, "compare_returns", {"tickers": ["AAPL", "TSLA", "JPM"], "start": "2026-06-01", "end": "2026-11-20"}
    ).data
    expected = {}
    for t in ("AAPL", "TSLA", "JPM"):
        c = closes(wh, t, date(2026, 6, 1), date(2026, 11, 20))
        expected[t] = round((c[-1] / c[0] - 1) * 100, 2)

    assert [r["ticker"] for r in data["rows"]] == sorted(expected, key=expected.get, reverse=True)
    assert {r["ticker"]: r["returnPct"] for r in data["rows"]} == expected


def test_volatility_rank_is_every_stock_on_the_last_day(wh):
    data = run_tool(wh, "volatility_rank", {"window": 60}).data
    raw = wh.rows(
        "SELECT ticker, volatility_60d_annualized AS v FROM fct_daily_trading WHERE trading_date = ?", [wh.last_date]
    )

    assert len(data["rows"]) == 10
    assert [r["ticker"] for r in data["rows"]] == [r["ticker"] for r in sorted(raw, key=lambda r: r["v"], reverse=True)]


def test_macro_overlay_sets_the_series_beside_the_price(wh):
    data = run_tool(
        wh,
        "macro_overlay",
        {"ticker": "JPM", "series": "treasury_yield_10y", "start": "2026-10-01", "end": "2026-10-31"},
    ).data
    raw = wh.rows(
        "SELECT treasury_yield_10y AS y FROM fct_daily_trading "
        "WHERE ticker = 'JPM' AND trading_date BETWEEN '2026-10-01' AND '2026-10-31' ORDER BY trading_date"
    )
    assert [p["series"] for p in data["points"]] == [round(r["y"], 3) for r in raw]
    assert data["seriesName"] == "10-year Treasury yield"


def test_macro_snapshot_has_every_series(wh):
    data = run_tool(wh, "macro_snapshot", {}).data
    assert len(data["rows"]) == 7
    assert all(r["value"] is not None for r in data["rows"])


@pytest.mark.parametrize(
    ("name", "arguments", "says"),
    [
        ("price_history", {"ticker": "XYZ"}, "Unknown ticker"),
        ("price_history", {"ticker": "AAPL", "start": "2026-11-01", "end": "2026-10-01"}, "is after"),
        ("price_history", {"ticker": "AAPL", "start": "2020-01-01", "end": "2020-02-01"}, "covers"),
        ("compare_returns", {"tickers": ["AAPL"]}, "not valid"),
        ("volatility_rank", {"window": 30}, "not valid"),
        ("macro_overlay", {"ticker": "AAPL", "series": "gold"}, "not valid"),
        ("price_history", {"ticker": "AAPL", "sql": "DROP TABLE x"}, "not valid"),
        ("run_sql", {}, "no tool"),
    ],
)
def test_bad_arguments_are_explained_to_the_model(wh, name, arguments, says):
    with pytest.raises(ToolError, match=says):
        run_tool(wh, name, arguments)


def test_declarations_describe_every_tool_and_parameter():
    declarations = tool_declarations()
    assert [d["name"] for d in declarations] == list(TOOLS)
    for d in declarations:
        assert d["description"]
        assert "$ref" not in str(d["parameters"])
        for name, schema in d["parameters"].get("properties", {}).items():
            assert schema.get("description") or schema.get("enum"), f"{d['name']}.{name} has no description"


def test_the_warehouse_is_read_only(wh):
    with pytest.raises(Exception, match=r"read-only|read only"):
        wh.rows("DELETE FROM dim_company")


def test_the_52_week_position_is_in_percent(wh):
    latest = run_tool(wh, "price_history", {"ticker": "AAPL"}).data["latest"]
    assert latest["low52w"] <= latest["close"] <= latest["high52w"]
    expected = (latest["close"] - latest["low52w"]) / (latest["high52w"] - latest["low52w"]) * 100
    assert latest["position52w"] == pytest.approx(expected, abs=0.2)


def test_every_figure_a_tool_returns_has_a_format(wh):
    results = [
        run_tool(wh, "price_history", {"ticker": "AAPL"}).data,
        run_tool(wh, "compare_returns", {"tickers": ["AAPL", "MSFT"]}).data,
        run_tool(wh, "volatility_rank", {}).data,
        run_tool(wh, "macro_snapshot", {}).data,
        run_tool(wh, "macro_overlay", {"ticker": "MSFT", "series": "cpi"}).data,
    ]

    def figures(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                yield from figures(v, f"{path}/{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from figures(v, f"{path}/{i}")
        elif isinstance(node, int | float) and not isinstance(node, bool):
            yield path

    for data in results:
        for path in figures(data):
            assert figure_format(data, path) is not None, path


def test_a_rate_is_a_percent_and_the_consumer_price_index_a_number(wh):
    snapshot = run_tool(wh, "macro_snapshot", {}).data
    formats = {row["series"]: figure_format(snapshot, f"/rows/{i}/value") for i, row in enumerate(snapshot["rows"])}
    assert formats.pop("cpi") == "number"
    assert set(formats.values()) == {"percent"}

    overlay = {"r2": run_tool(wh, "macro_overlay", {"ticker": "MSFT", "series": "cpi"}).data}
    assert figure_format(overlay, "/r2/latest/series") == "number"
    assert figure_format(overlay, "/r2/latest/close") == "currency"
    rate = {"r1": run_tool(wh, "macro_overlay", {"ticker": "MSFT", "series": "fed_funds_rate"}).data}
    assert figure_format(rate, "/r1/latest/series") == "percent"


def test_every_field_a_tool_returns_has_a_meaning(wh):
    """Except the ones that name a thing rather than measure it."""
    named = {"ticker", "name", "company_name", "sector", "industry", "market_cap_category", "exchange", "country"}
    named |= {"date", "rows", "points", "latest", "tool"}
    results = [
        run_tool(wh, "price_history", {"ticker": "AAPL"}).data,
        run_tool(wh, "compare_returns", {"tickers": ["AAPL", "MSFT"]}).data,
        run_tool(wh, "volatility_rank", {}).data,
        run_tool(wh, "macro_snapshot", {}).data,
        run_tool(wh, "macro_overlay", {"ticker": "MSFT", "series": "cpi"}).data,
    ]

    def keys(node) -> set[str]:
        if isinstance(node, dict):
            return set(node).union(*(keys(v) for v in node.values()))
        if isinstance(node, list):
            return set().union(*(keys(v) for v in node))
        return set()

    for data in results:
        meanings = field_meanings(data)
        unexplained = keys(data) - named - set(meanings)
        assert not unexplained, unexplained
        assert set(meanings) <= set(FIELD_MEANINGS)
