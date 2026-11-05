"""Simulate games and log one row per move, with the acting player's state just before it.

Usage:
    python -m hexstrat.simulate --games 100 --seed 42 --out data/raw

Writes, per run:
    <out>/moves_<run_id>.parquet        one row per move (see MOVE_COLUMNS)
    <out>/board_tiles_<run_id>.parquet  one row per (game, node, adjacent land tile)
    <out>/board_ports_<run_id>.parquet  one row per (game, port node)
    <out>/run_<run_id>.json        run record: lineup, versions, seed, game count, date
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from catanatron import Color, Game, RandomPlayer
from catanatron.players.weighted_random import WeightedRandomPlayer
from catanatron.state_functions import (
    get_actual_victory_points,
    get_player_buildings,
    player_num_dev_cards,
    player_num_resource_cards,
)

RESOURCES = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]

BOT_TYPES = {
    "R": RandomPlayer,
    "W": WeightedRandomPlayer,
}

MOVE_COLUMNS = [
    "run_id",
    "game_id",
    "turn",
    "move_index",
    "player",
    "seat",
    "action_type",
    "action_value",
    "is_initial_build",
    *[f"res_{r.lower()}" for r in RESOURCES],
    "settlements",
    "cities",
    "points",
    "dev_cards",
    "won",
    "game_finished",
]


@dataclass
class RunRecord:
    run_id: str
    lineup: list[str]
    seed: int
    num_games: int
    catanatron_version: str
    created_at: str
    games_finished: int = 0
    wins_by_bot: dict[str, int] = field(default_factory=dict)


def _jsonable(value):
    """Turn an action value (tuples, enums, None) into plain JSON types."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def _snapshot(game: Game, color: Color) -> dict:
    """The acting player's state just before their move."""
    state = game.state
    row = {f"res_{r.lower()}": player_num_resource_cards(state, color, r) for r in RESOURCES}
    row["settlements"] = len(get_player_buildings(state, color, "SETTLEMENT"))
    row["cities"] = len(get_player_buildings(state, color, "CITY"))
    row["points"] = get_actual_victory_points(state, color)
    row["dev_cards"] = player_num_dev_cards(state, color)
    return row


def board_rows(game: Game, run_id: str) -> tuple[list[dict], list[dict]]:
    """The board is reshuffled every game, so record it: one row per (node, adjacent land tile), and port nodes."""
    catan_map = game.state.board.map
    tiles = []
    for tile in catan_map.land_tiles.values():
        for node_id in tile.nodes.values():
            tiles.append(
                {
                    "run_id": run_id,
                    "game_id": game.id,
                    "node_id": node_id,
                    "tile_id": tile.id,
                    "resource": tile.resource or "DESERT",
                    "number": tile.number,
                }
            )
    ports = [
        {"run_id": run_id, "game_id": game.id, "node_id": node_id, "port_resource": resource or "ANY"}
        for resource, node_ids in catan_map.port_nodes.items()
        for node_id in node_ids
    ]
    return tiles, ports


def play_and_log(game: Game, run_id: str) -> tuple[list[dict], Color | None]:
    """Play one game, returning its move rows and the winning color (None if it hit the turn limit)."""
    game_id = game.id
    rows: list[dict] = []

    def logging_decide(player, game, playable_actions):
        action = player.decide(game, playable_actions)
        rows.append(
            {
                "run_id": run_id,
                "game_id": game_id,
                "turn": game.state.num_turns,
                "move_index": len(rows),
                "player": player.color.value,
                "seat": game.state.color_to_index[player.color],
                "action_type": action.action_type.value,
                "action_value": json.dumps(_jsonable(action.value)),
                "is_initial_build": game.state.is_initial_build_phase,
                **_snapshot(game, player.color),
            }
        )
        return action

    winner = game.play(decide_fn=logging_decide)
    for row in rows:
        row["won"] = winner is not None and row["player"] == winner.value
        row["game_finished"] = winner is not None
    return rows, winner


def simulate(num_games: int, seed: int, lineup: list[str], out_dir: Path) -> RunRecord:
    if len(lineup) != 4 or any(b not in BOT_TYPES for b in lineup):
        raise ValueError(f"lineup must be 4 of {sorted(BOT_TYPES)}, got {lineup}")

    run_id = uuid.uuid4().hex[:12]
    record = RunRecord(
        run_id=run_id,
        lineup=lineup,
        seed=seed,
        num_games=num_games,
        catanatron_version=version("catanatron"),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    bot_by_color = dict(zip((c.value for c in colors), lineup))
    game_seeds = random.Random(seed).sample(range(2**31), num_games)

    all_rows: list[dict] = []
    tile_rows: list[dict] = []
    port_rows: list[dict] = []
    for game_seed in game_seeds:
        players = [BOT_TYPES[bot](color) for bot, color in zip(lineup, colors)]
        game = Game(players, seed=game_seed)  # Game shuffles seat order using the seed
        tiles, ports = board_rows(game, run_id)
        tile_rows.extend(tiles)
        port_rows.extend(ports)
        rows, winner = play_and_log(game, run_id)
        all_rows.extend(rows)
        if winner is not None:
            record.games_finished += 1
            bot = bot_by_color[winner.value]
            record.wins_by_bot[bot] = record.wins_by_bot.get(bot, 0) + 1

    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_rows, columns=MOVE_COLUMNS).to_parquet(out_dir / f"moves_{run_id}.parquet", index=False)
    pd.DataFrame(tile_rows).astype({"number": "Int64"}).to_parquet(out_dir / f"board_tiles_{run_id}.parquet", index=False)
    pd.DataFrame(port_rows).to_parquet(out_dir / f"board_ports_{run_id}.parquet", index=False)
    (out_dir / f"run_{run_id}.json").write_text(json.dumps(asdict(record), indent=2))
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lineup", default="R,W,R,R", help="4 bot codes: R=random, W=weighted random")
    parser.add_argument("--out", type=Path, default=Path("data/raw"))
    args = parser.parse_args()

    record = simulate(args.games, args.seed, args.lineup.split(","), args.out)
    print(json.dumps(asdict(record), indent=2))


if __name__ == "__main__":
    main()
