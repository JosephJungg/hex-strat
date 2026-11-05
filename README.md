# hex-strat

Simulated hex-board strategy games → a tested data pipeline → a model that recommends opening settlement placements, measured by a bot's win rate against baseline bots.

Games are simulated with [Catanatron](https://github.com/bcollazo/catanatron), an open-source engine. This project is not affiliated with the board game's publisher.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

Tested on Python 3.13 with Catanatron 3.2.1. The PyPI package is the core engine only; it has no `catanatron-play` CLI, so hexstrat drives games through the Python API.

## Simulate games

```bash
.venv/bin/python -m hexstrat.simulate --games 100 --seed 42 --lineup R,W,R,R --out data/raw
```

Bots: `R` = random, `W` = weighted random. Seat order is shuffled per game. Each run writes:

- `moves_<run_id>.parquet`: one row per move, with the acting player's state just before it.
- `run_<run_id>.json`: run record with lineup, seed, game count, Catanatron version, date and wins per bot.

| Column | Meaning |
| --- | --- |
| `run_id`, `game_id`, `turn`, `move_index` | Where the move sits |
| `player`, `seat` | Acting color and seat (0 = first) |
| `action_type`, `action_value` | The move; value is JSON (node id, edge, trade, …) |
| `is_initial_build` | True for the opening placement phase |
| `res_wood` … `res_ore`, `settlements`, `cities`, `points`, `dev_cards` | Acting player's state before the move |
| `won`, `game_finished` | Training label; false for games that hit the turn limit |

100 games take about 2 seconds and give about 87,000 move rows.

## Next: the minimal end-to-end slice

Before building more infrastructure, get one thin path working all the way through:

1. **Data**: 100 games from `hexstrat.simulate` (done).
2. **Warehouse**: load the Parquet file into DuckDB.
3. **dbt**: one model, `fct_opening_placements`, with one row per opening settlement (game, player, seat, node, won).
4. **Model**: a trivial placement scorer, such as the win rate per node, split by `game_id`.
5. **Bot**: a player that picks the highest-scoring node in the opening and plays randomly afterwards; compare its win rate against the random bot.
