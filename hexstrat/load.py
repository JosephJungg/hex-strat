"""Load raw simulator output into the warehouse's `raw` schema, as-is (the L in ELT).

Usage:
    python -m hexstrat.load --src data/raw --db warehouse/hexstrat.duckdb

Full refresh for now: each table is rebuilt from every file in --src.
Incremental loads come with the Airflow work (weeks 8-10).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

TABLES = {
    "moves": "moves_*.parquet",
    "board_tiles": "board_tiles_*.parquet",
    "board_ports": "board_ports_*.parquet",
}


def load(src: Path, db: Path) -> dict[str, int]:
    db.parent.mkdir(parents=True, exist_ok=True)
    counts = {}
    with duckdb.connect(str(db)) as con:
        con.execute("create schema if not exists raw")
        for table, pattern in TABLES.items():
            con.execute(
                f"create or replace table raw.{table} as select * from read_parquet(?, union_by_name = true)",
                [str(src / pattern)],
            )
            counts[table] = con.execute(f"select count(*) from raw.{table}").fetchone()[0]
        con.execute(
            "create or replace table raw.runs as select * from read_json_auto(?)",
            [str(src / "run_*.json")],
        )
        counts["runs"] = con.execute("select count(*) from raw.runs").fetchone()[0]
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type=Path, default=Path("data/raw"))
    parser.add_argument("--db", type=Path, default=Path("warehouse/hexstrat.duckdb"))
    args = parser.parse_args()
    for table, n in load(args.src, args.db).items():
        print(f"raw.{table}: {n:,} rows")


if __name__ == "__main__":
    main()
