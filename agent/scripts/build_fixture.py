"""Builds the fixture warehouse the agent's tests run against.

It runs the real pipeline of data-engineer-finance-analytics, so the fixture
has the marts exactly as that project's dbt models build them, then keeps the
last stretch of trading days in a small DuckDB file under tests/fixtures.

Run it with that project's environment, from this repository's root:

    uv run --project ../data-engineer-finance-analytics \\
        python agent/scripts/build_fixture.py --pipeline ../data-engineer-finance-analytics

Prices come from Yahoo Finance through the pipeline's own extract. FRED series
are read from FRED's public CSV download, which needs no API key, and written
in the shape the pipeline's FRED extract writes, so its loader and dbt models
take them unchanged.
"""

import argparse
import io
import os
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "warehouse.duckdb"
TRADING_DAYS_KEPT = 130
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd={start}"


def extract_fred_without_key(pipeline: Path) -> None:
    import pandas as pd
    from extract.economic_indicators import FRED_SERIES, _infer_frequency

    start = (date.today() - timedelta(days=365 * 5)).isoformat()
    frames = []
    for series_id, description in FRED_SERIES.items():
        with urllib.request.urlopen(FRED_CSV.format(series=series_id, start=start), timeout=60) as response:
            raw = pd.read_csv(io.BytesIO(response.read()), na_values=["."])
        raw.columns = ["observation_date", "value"]
        raw["observation_date"] = pd.to_datetime(raw["observation_date"])
        observed = raw.dropna(subset=["value"]).set_index("observation_date")["value"]
        frame = observed.reset_index()
        frame.columns = ["observation_date", "value"]
        frame["series_id"] = series_id
        frame["series_name"] = description
        frame["frequency"] = _infer_frequency(observed)
        frame["extracted_at"] = datetime.now().isoformat()
        frames.append(frame)
        print(f"FRED {series_id}: {len(frame)} observations")
    out = pipeline / "data" / "raw"
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(frames, ignore_index=True).to_parquet(out / "economic_indicators.parquet", index=False)


def copy_marts(source: Path) -> None:
    import duckdb

    FIXTURE.unlink(missing_ok=True)
    con = duckdb.connect(str(FIXTURE))
    con.execute(f"ATTACH '{source}' AS pipeline (READ_ONLY)")
    schema = con.execute(
        "SELECT table_schema FROM information_schema.tables "
        "WHERE table_catalog = 'pipeline' AND table_name = 'fct_daily_trading'"
    ).fetchone()[0]
    con.execute(
        f"""
        CREATE TABLE fct_daily_trading AS
        WITH kept AS (
            SELECT DISTINCT trading_date FROM pipeline.{schema}.fct_daily_trading
            ORDER BY trading_date DESC LIMIT {TRADING_DAYS_KEPT}
        )
        SELECT * FROM pipeline.{schema}.fct_daily_trading
        WHERE trading_date IN (SELECT trading_date FROM kept)
        ORDER BY ticker, trading_date
        """
    )
    con.execute(f"CREATE TABLE dim_company AS SELECT * FROM pipeline.{schema}.dim_company ORDER BY ticker")
    con.execute(
        f"""
        CREATE TABLE dim_date AS SELECT * FROM pipeline.{schema}.dim_date
        WHERE calendar_date BETWEEN (SELECT min(trading_date) FROM fct_daily_trading)
                                AND (SELECT max(trading_date) FROM fct_daily_trading)
        ORDER BY calendar_date
        """
    )
    for table in ("fct_daily_trading", "dim_company", "dim_date"):
        print(table, con.execute(f"SELECT count(*) FROM {table}").fetchone()[0], "rows")
    con.execute("DETACH pipeline")
    con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pipeline", type=Path, required=True, help="data-engineer-finance-analytics checkout")
    pipeline = parser.parse_args().pipeline.resolve()

    os.chdir(pipeline)
    sys.path.insert(0, str(pipeline))
    os.environ.update(TARGET="local", DBT_TARGET="local")
    database = pipeline / "data" / "processed" / "finance.duckdb"
    os.environ["FINANCE_DB_PATH"] = str(database)

    from extract.stock_prices import extract_company_info, extract_stock_prices

    extract_stock_prices()
    extract_company_info()
    extract_fred_without_key(pipeline)
    for step in ("load", "transform"):
        subprocess.run([sys.executable, "main.py", step], check=True)
    copy_marts(database)


if __name__ == "__main__":
    main()
