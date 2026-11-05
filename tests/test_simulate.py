import json

import pandas as pd

from hexstrat.simulate import MOVE_COLUMNS, simulate


def _run(tmp_path, seed=7, games=5):
    record = simulate(games, seed, ["R", "W", "R", "R"], tmp_path)
    moves = pd.read_parquet(tmp_path / f"moves_{record.run_id}.parquet")
    return record, moves


def test_writes_moves_and_run_record(tmp_path):
    record, moves = _run(tmp_path)
    assert list(moves.columns) == MOVE_COLUMNS
    assert moves["game_id"].nunique() == 5
    run = json.loads((tmp_path / f"run_{record.run_id}.json").read_text())
    assert run["num_games"] == 5 and run["catanatron_version"] == "3.2.1"


def test_one_winner_per_finished_game(tmp_path):
    _, moves = _run(tmp_path)
    finished = moves[moves["game_finished"]]
    winners = finished[finished["won"]].groupby("game_id")["player"].nunique()
    assert (winners == 1).all()
    assert len(winners) == finished["game_id"].nunique()


def test_opening_is_two_settlements_and_two_roads_per_player(tmp_path):
    _, moves = _run(tmp_path)
    opening = moves[moves["is_initial_build"]]
    per_player = opening.groupby(["game_id", "player"])["action_type"].value_counts().unstack()
    assert (per_player["BUILD_SETTLEMENT"] == 2).all()
    assert (per_player["BUILD_ROAD"] == 2).all()
    first = moves[moves["move_index"] == 0]
    assert (first["action_type"] == "BUILD_SETTLEMENT").all()
    assert (first["points"] == 0).all()


def test_same_seed_reproduces_moves(tmp_path):
    _, a = _run(tmp_path / "a", seed=11, games=3)
    _, b = _run(tmp_path / "b", seed=11, games=3)
    cols = [c for c in MOVE_COLUMNS if c not in ("run_id", "game_id")]
    pd.testing.assert_frame_equal(a[cols], b[cols])
