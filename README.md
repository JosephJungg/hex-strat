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
- `board_tiles_<run_id>.parquet`: one row per (game, node, adjacent land tile). The board is reshuffled every game, so a node id alone says nothing about a spot.
- `board_ports_<run_id>.parquet`: one row per (game, port node).
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

## End-to-end slice

One thin path from simulation to a bot that plays, run from the repo root:

```bash
.venv/bin/python -m hexstrat.simulate --games 1000 --seed 42 --out data/raw   # ~18 s
.venv/bin/python -m hexstrat.load                                             # Parquet -> DuckDB raw schema
(cd dbt && ../.venv/bin/dbt build --profiles-dir .)                            # models + 13 tests
.venv/bin/python -m hexstrat.scorer                                           # train, report held-out metrics
.venv/bin/python -m hexstrat.bot --games 2000 --opponents R                   # win rate with 95% CI
```

| Stage | What it does |
| --- | --- |
| `hexstrat.load` | Loads raw files into `warehouse/hexstrat.duckdb`, schema `raw` |
| `stg_*` (dbt) | Typed staging views over raw tables; fault handling lands here in weeks 5–7 |
| `int_node_features` (dbt) | Per game and node: total pips, distinct resources, pips per resource, port |
| `fct_opening_placements` (dbt) | One row per opening settlement in finished games, with its features and `won` |
| `hexstrat.scorer` | Smoothed win rate by (pips, distinct resources); train/test split by `game_id` |
| `hexstrat.bot` | Picks the best-scoring opening spot, plays randomly afterwards |

The bot computes node features in Python (`hexstrat/features.py`) while training data computes them in SQL; `tests/test_features.py` runs dbt and checks both agree.

### Results (1,000 training games, seed 42)

- Spot quality predicts winning: players whose opening spot touches 13+ pips won 52% of games; spots touching no numbers won 8% (Nov 5 run).
- Scorer on 182 held-out games: AUC 0.69, log loss 0.523 vs 0.562 for always predicting 25%.
- Bot vs 3 random bots: **47.4% win rate** (95% CI 45.2–49.5%, 2,000 games; Nov 12 run).
- Same-seat control: a random player in the bot's seat, with the same game seeds, won 24.8% (95% CI 23.0–26.8%, 1,998 finished games). The bot differs from it only in its two opening settlements, so the gap comes from placement.
- Bot vs 3 weighted-random bots: 23.8% (95% CI 22.0–25.7%; Nov 5 run), no better than chance. Good openings don't make up for random play afterwards.

Simulation is seeded, but bot moves after the opening use Python's unseeded global RNG, so evaluation results vary slightly between runs (the Nov 5 run gave 48.4% vs random bots).
