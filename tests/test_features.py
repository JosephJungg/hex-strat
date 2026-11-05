"""The bot computes node features in Python; training data computes them in dbt SQL. They must agree."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd
from catanatron import Color, Game, RandomPlayer

from hexstrat.features import node_features, pips
from hexstrat.simulate import board_rows

REPO = Path(__file__).resolve().parents[1]
DBT = Path(sys.executable).parent / "dbt"


def test_pips():
    assert [pips(n) for n in (2, 3, 6, 7, 8, 12, None)] == [1, 2, 5, 6, 5, 1, 0]


def test_python_features_match_dbt(tmp_path):
    games = [
        Game([RandomPlayer(c) for c in (Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE)], seed=s)
        for s in (1, 2, 3)
    ]
    tiles, ports = [], []
    for g in games:
        t, p = board_rows(g, "test")
        tiles += t
        ports += p

    db = tmp_path / "test.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("create schema raw")
        tiles_df = pd.DataFrame(tiles).astype({"number": "Int64"})
        ports_df = pd.DataFrame(ports)
        con.execute("create table raw.board_tiles as select * from tiles_df")
        con.execute("create table raw.board_ports as select * from ports_df")

    project = tmp_path / "dbt"
    shutil.copytree(REPO / "dbt", project, ignore=shutil.ignore_patterns("target", "logs", "dbt_packages"))
    subprocess.run(
        [str(DBT), "run", "--select", "+int_node_features", "--profiles-dir", ".", "--quiet"],
        cwd=project,
        env={**os.environ, "HEXSTRAT_DB": str(db)},
        check=True,
    )

    with duckdb.connect(str(db), read_only=True) as con:
        sql = con.sql("select * from intermediate.int_node_features").df().set_index(["game_id", "node_id"])

    checked = 0
    for g in games:
        for node_id in g.state.board.map.adjacent_tiles:
            py = node_features(g.state.board.map, node_id)
            row = sql.loc[(g.id, node_id)]
            for col, value in py.items():
                expected = None if pd.isna(row[col]) else row[col]
                assert value == expected, (g.id, node_id, col)
            checked += 1
    assert checked == 3 * 54
