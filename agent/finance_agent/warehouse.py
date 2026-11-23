"""Read-only access to the finance warehouse built by data-engineer-finance-analytics."""

import os
from datetime import date
from pathlib import Path

import duckdb

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "warehouse.duckdb"


class Warehouse:
    """The dbt marts: `fct_daily_trading`, `dim_company` and `dim_date`.

    Opened read-only: nothing the agent does can change the data. Every query
    is a fixed SQL statement with its values passed as parameters.
    """

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path or os.environ.get("FC_WAREHOUSE", DEFAULT_PATH))
        self._con = duckdb.connect(str(self.path), read_only=True)
        self.tickers: frozenset[str] = frozenset(
            row[0] for row in self._con.execute("SELECT ticker FROM dim_company").fetchall()
        )
        first, last = self._con.execute("SELECT min(trading_date), max(trading_date) FROM fct_daily_trading").fetchone()
        self.first_date: date = first
        self.last_date: date = last

    def rows(self, sql: str, params: list | None = None) -> list[dict]:
        cursor = self._con.execute(sql, params or [])
        columns = [d[0] for d in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    def close(self) -> None:
        self._con.close()
