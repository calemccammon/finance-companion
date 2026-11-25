"""The analyses the model may ask for.

Each tool takes typed arguments, runs one fixed, parameterised query against
the dbt marts, and returns typed rows. The model chooses the tools and their
arguments; it never writes SQL, and the figures it lays out come from here.
"""

from collections.abc import Callable
from datetime import date, timedelta
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from finance_agent.warehouse import Warehouse


class ToolError(ValueError):
    """The arguments ask for something the warehouse does not have. The message is for the model."""


class MacroSeries(StrEnum):
    """The FRED series in the warehouse, by the column that holds each."""

    fed_funds_rate = "fed_funds_rate"
    cpi = "cpi"
    unemployment_rate = "unemployment_rate"
    treasury_yield_10y = "treasury_yield_10y"
    gdp_growth_rate = "gdp_growth_rate"
    breakeven_inflation_10y = "breakeven_inflation_10y"
    real_yield_10y = "real_yield_10y"


MACRO_NAMES = {
    MacroSeries.fed_funds_rate: "Federal funds rate",
    MacroSeries.cpi: "Consumer price index",
    MacroSeries.unemployment_rate: "Unemployment rate",
    MacroSeries.treasury_yield_10y: "10-year Treasury yield",
    MacroSeries.gdp_growth_rate: "Real GDP growth",
    MacroSeries.breakeven_inflation_10y: "10-year breakeven inflation",
    MacroSeries.real_yield_10y: "10-year real yield",
}

# How each figure the tools return must be drawn: the `format` of a MetricCard or
# RankedBars showing it. "percent" is a figure already in percent; "change" a change
# in percent, drawn with its sign.
FIELD_FORMATS = {
    **dict.fromkeys(("close", "startClose", "endClose", "high52w", "low52w", "sma30", "sma90"), "currency"),
    **dict.fromkeys(("changePct", "dailyReturnPct", "returnPct"), "change"),
    **dict.fromkeys(("position52w", "volatility20d", "volatility"), "percent"),
    "windowDays": "number",
}
# A macro series' figure (a row's `value`, an overlay's `series`) is a rate in percent,
# except the consumer price index, which is an index.
MACRO_FIELDS = frozenset({"value", "series"})


def figure_format(data: dict, path: str) -> str | None:
    """The format the figure at [path] in [data] must be drawn with; None if it is not known."""
    keys = path.strip("/").split("/")
    field = keys[-1]
    if field in MACRO_FIELDS:
        # The nearest object on the way that names its series: a snapshot's row, an overlay.
        node, series = data, None
        for key in [None, *keys[:-1]]:
            if key is not None:
                node = node.get(key) if isinstance(node, dict) else (node[int(key)] if key.isdigit() else None)
            if isinstance(node, dict) and isinstance(node.get("series"), str):
                series = node["series"]
        if series is None:
            return None
        return "number" if series == MacroSeries.cpi else "percent"
    return FIELD_FORMATS.get(field)


Ticker = Annotated[str, Field(description="A ticker symbol, such as AAPL.")]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Range(_Args):
    start: date | None = Field(None, description="First trading day to include. Defaults to 90 days before `end`.")
    end: date | None = Field(None, description="Last trading day to include. Defaults to the latest in the warehouse.")


class CompanyProfileArgs(_Args):
    ticker: Ticker


class PriceHistoryArgs(_Range):
    ticker: Ticker


class CompareReturnsArgs(_Range):
    tickers: list[Ticker] = Field(..., min_length=2, max_length=10, description="Two to ten tickers to compare.")


class VolatilityRankArgs(_Args):
    window: int = Field(20, description="Days of returns the volatility is measured over: 20 or 60.")

    @field_validator("window")
    @classmethod
    def _known_window(cls, value: int) -> int:
        if value not in (20, 60):
            raise ValueError("window must be 20 or 60")
        return value


class MacroOverlayArgs(_Range):
    ticker: Ticker
    series: MacroSeries = Field(..., description="The economic series to set beside the price.")


class MacroSnapshotArgs(_Args):
    pass


class ToolResult(BaseModel):
    """What a tool found: plain values for the surface's data model, keyed by name."""

    tool: str
    data: dict[str, Any]


class Tool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    args: type[_Args]
    run: Callable[[Warehouse, Any], ToolResult]


# --- the queries -------------------------------------------------------------


def _ticker(wh: Warehouse, ticker: str) -> str:
    symbol = ticker.strip().upper()
    if symbol not in wh.tickers:
        raise ToolError(f"Unknown ticker {ticker!r}. The warehouse has: {', '.join(sorted(wh.tickers))}.")
    return symbol


def _range(wh: Warehouse, args: _Range) -> tuple[date, date]:
    end = args.end or wh.last_date
    start = args.start or end - timedelta(days=90)
    if start > end:
        raise ToolError(f"start {start} is after end {end}.")
    if end < wh.first_date or start > wh.last_date:
        raise ToolError(f"The warehouse covers {wh.first_date} to {wh.last_date}.")
    return max(start, wh.first_date), min(end, wh.last_date)


def _round(value: float | None, places: int = 4) -> float | None:
    return None if value is None else round(float(value), places)


def company_profile(wh: Warehouse, args: CompanyProfileArgs) -> ToolResult:
    ticker = _ticker(wh, args.ticker)
    row = wh.rows(
        "SELECT ticker, company_name, sector, industry, market_cap_category, exchange, country "
        "FROM dim_company WHERE ticker = ?",
        [ticker],
    )[0]
    return ToolResult(tool="company_profile", data=row)


def price_history(wh: Warehouse, args: PriceHistoryArgs) -> ToolResult:
    ticker = _ticker(wh, args.ticker)
    start, end = _range(wh, args)
    rows = wh.rows(
        "SELECT trading_date, close_price, sma_30d, sma_90d, daily_return_pct, high_52w, low_52w, "
        "price_position_52w, volatility_20d_annualized "
        "FROM fct_daily_trading WHERE ticker = ? AND trading_date BETWEEN ? AND ? ORDER BY trading_date",
        [ticker, start, end],
    )
    if not rows:
        raise ToolError(f"No trading days for {ticker} between {start} and {end}.")
    first, last = rows[0], rows[-1]
    return ToolResult(
        tool="price_history",
        data={
            "ticker": ticker,
            "start": first["trading_date"].isoformat(),
            "end": last["trading_date"].isoformat(),
            "latest": {
                "close": _round(last["close_price"], 2),
                "dailyReturnPct": _round(last["daily_return_pct"], 2),
                "changePct": _round((last["close_price"] / first["close_price"] - 1) * 100, 2),
                "high52w": _round(last["high_52w"], 2),
                "low52w": _round(last["low_52w"], 2),
                # Where the close sits between the 52-week low (0) and high (100), in percent.
                "position52w": _round(last["price_position_52w"] * 100, 1),
                "volatility20d": _round(last["volatility_20d_annualized"], 2),
            },
            "points": [
                {
                    "date": r["trading_date"].isoformat(),
                    "close": _round(r["close_price"], 2),
                    "sma30": _round(r["sma_30d"], 2),
                    "sma90": _round(r["sma_90d"], 2),
                }
                for r in rows
            ],
        },
    )


def compare_returns(wh: Warehouse, args: CompareReturnsArgs) -> ToolResult:
    tickers = sorted({_ticker(wh, t) for t in args.tickers})
    start, end = _range(wh, args)
    rows = wh.rows(
        """
        SELECT ticker, any_value(company_name) AS company_name,
               arg_min(close_price, trading_date) AS first_close,
               arg_max(close_price, trading_date) AS last_close,
               min(trading_date) AS first_day, max(trading_date) AS last_day
        FROM fct_daily_trading
        WHERE ticker IN (SELECT unnest(?)) AND trading_date BETWEEN ? AND ?
        GROUP BY ticker
        """,
        [tickers, start, end],
    )
    ranked = sorted(
        (
            {
                "ticker": r["ticker"],
                "name": r["company_name"],
                "startClose": _round(r["first_close"], 2),
                "endClose": _round(r["last_close"], 2),
                "returnPct": _round((r["last_close"] / r["first_close"] - 1) * 100, 2),
            }
            for r in rows
        ),
        key=lambda r: r["returnPct"],
        reverse=True,
    )
    return ToolResult(
        tool="compare_returns",
        data={"start": start.isoformat(), "end": end.isoformat(), "rows": ranked},
    )


def volatility_rank(wh: Warehouse, args: VolatilityRankArgs) -> ToolResult:
    column = {20: "volatility_20d_annualized", 60: "volatility_60d_annualized"}[args.window]
    rows = wh.rows(
        f"SELECT ticker, company_name, {column} AS volatility FROM fct_daily_trading "
        "WHERE trading_date = ? ORDER BY volatility DESC",
        [wh.last_date],
    )
    return ToolResult(
        tool="volatility_rank",
        data={
            "asOf": wh.last_date.isoformat(),
            "windowDays": args.window,
            "rows": [
                {"ticker": r["ticker"], "name": r["company_name"], "volatility": _round(r["volatility"], 2)}
                for r in rows
            ],
        },
    )


def macro_overlay(wh: Warehouse, args: MacroOverlayArgs) -> ToolResult:
    ticker = _ticker(wh, args.ticker)
    start, end = _range(wh, args)
    column = args.series.value
    rows = wh.rows(
        f"SELECT trading_date, close_price, {column} AS series_value FROM fct_daily_trading "
        "WHERE ticker = ? AND trading_date BETWEEN ? AND ? ORDER BY trading_date",
        [ticker, start, end],
    )
    if not rows:
        raise ToolError(f"No trading days for {ticker} between {start} and {end}.")
    return ToolResult(
        tool="macro_overlay",
        data={
            "ticker": ticker,
            "series": column,
            "seriesName": MACRO_NAMES[args.series],
            "latest": {"close": _round(rows[-1]["close_price"], 2), "series": _round(rows[-1]["series_value"], 3)},
            "points": [
                {
                    "date": r["trading_date"].isoformat(),
                    "close": _round(r["close_price"], 2),
                    "series": _round(r["series_value"], 3),
                }
                for r in rows
            ],
        },
    )


def macro_snapshot(wh: Warehouse, args: MacroSnapshotArgs) -> ToolResult:
    columns = ", ".join(s.value for s in MacroSeries)
    # Every ticker carries the same macro columns on a given day; one is enough.
    row = wh.rows(
        f"SELECT {columns} FROM fct_daily_trading WHERE trading_date = ? ORDER BY ticker LIMIT 1",
        [wh.last_date],
    )[0]
    return ToolResult(
        tool="macro_snapshot",
        data={
            "asOf": wh.last_date.isoformat(),
            "rows": [
                {"series": s.value, "name": MACRO_NAMES[s], "value": _round(row[s.value], 3)} for s in MacroSeries
            ],
        },
    )


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            name="company_profile",
            description="Who a company is: name, sector, industry and size.",
            args=CompanyProfileArgs,
            run=company_profile,
        ),
        Tool(
            name="price_history",
            description="One stock's daily closes over a date range, with its 30- and 90-day moving averages, "
            "and its latest close, daily return, change over the range, 52-week range and volatility.",
            args=PriceHistoryArgs,
            run=price_history,
        ),
        Tool(
            name="compare_returns",
            description="How much each of several stocks rose or fell over the same date range, best first.",
            args=CompareReturnsArgs,
            run=compare_returns,
        ),
        Tool(
            name="volatility_rank",
            description="Every stock in the warehouse ranked by annualised volatility on the latest trading day, "
            "most volatile first.",
            args=VolatilityRankArgs,
            run=volatility_rank,
        ),
        Tool(
            name="macro_overlay",
            description="One stock's daily closes beside an economic series over the same date range. "
            "Each day carries the latest figure of the series that had been published by then.",
            args=MacroOverlayArgs,
            run=macro_overlay,
        ),
        Tool(
            name="macro_snapshot",
            description="The latest published figure of each economic series in the warehouse.",
            args=MacroSnapshotArgs,
            run=macro_snapshot,
        ),
    ]
}


def run_tool(wh: Warehouse, name: str, arguments: dict) -> ToolResult:
    """Runs the tool [name] with [arguments] as the model sent them. Raises ToolError for the model to read."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"There is no tool {name!r}. The tools are: {', '.join(TOOLS)}.")
    try:
        args = tool.args.model_validate(arguments)
    except ValueError as e:
        raise ToolError(f"Arguments for {name} are not valid: {e}") from e
    return tool.run(wh, args)


def tool_declarations() -> list[dict]:
    """Each tool's name, purpose and parameters as JSON Schema, for the model.

    Made from the same argument models that validate the model's calls, so
    the two cannot drift apart.
    """
    return [
        {"name": t.name, "description": t.description, "parameters": _inline(t.args.model_json_schema())}
        for t in TOOLS.values()
    ]


def _inline(schema: dict) -> dict:
    """Replaces `$ref`s with the definitions they name; model APIs take a self-contained schema."""
    defs = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(dict(defs[node["$ref"].rsplit("/", 1)[-1]]))
            return {k: resolve(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [resolve(v) for v in node]
        return node

    return resolve(schema)
