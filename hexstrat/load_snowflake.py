"""Load raw simulator output into Snowflake's HEXSTRAT.RAW schema (internal stage + COPY INTO).

Usage:
    python -m hexstrat.load_snowflake --src data/raw

Reads SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER and SNOWFLAKE_PRIVATE_KEY_PATH from the environment.
"""

import os 
import snowflake.connector
import argparse
from pathlib import Path

TABLES = {"BOARD_PORTS": "board_ports", "BOARD_TILES": "board_tiles", "MOVES": "moves"}

def load(src: Path) -> dict[str, int]:
    src = src.resolve()
    output_dict = {}
    with snowflake.connector.connect(account = os.environ["SNOWFLAKE_ACCOUNT"],
                                 user = os.environ["SNOWFLAKE_USER"],
                                 private_key_file=os.environ['SNOWFLAKE_PRIVATE_KEY_PATH'],
                                 warehouse = "HEXSTRAT_WH", database = "HEXSTRAT", schema = "RAW",) as con:
        cur = con.cursor()
        cur.execute("create file format if not exists parquet_ff " \
                    "type = parquet ")
        cur.execute("create stage if not exists hexstrat_stage " \
                    "file_format = parquet_ff")
        for table, stage in TABLES.items():
            cur.execute(f"put file://{src}/{stage}_*.parquet @hexstrat_stage/{stage}/ overwrite = true")
            cur.execute(f"create or replace table {table} using template (select array_agg(object_construct(*))from table(infer_schema(location => '@hexstrat_stage/{stage}/'," \
            "file_format => 'parquet_ff', ignore_case => true)))")
            cur.execute(f"copy into {table} from @hexstrat_stage/{stage}/ match_by_column_name = case_insensitive")
            cur.execute(f"select count(*) from {table}")
            output_dict[table] = cur.fetchone()[0]
    return output_dict


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", type = Path, default = Path("data/raw"))
    args = parser.parse_args()
    for table, n in load(args.src).items():
        print(f"raw.{table}: {n} rows")

if __name__ == "__main__":
    main()