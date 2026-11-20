# hex-strat

Simulated Catan games → a tested data pipeline → a model that recommends opening settlement placements, measured by a bot's win rate against baseline bots.

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
(cd dbt && ../.venv/bin/dbt build --profiles-dir .)                            # models + 21 tests
.venv/bin/python -m hexstrat.scorer                                           # train, report held-out metrics
.venv/bin/python -m hexstrat.bot --games 2000 --opponents R                   # win rate with 95% CI
```

| Stage | What it does |
| --- | --- |
| `hexstrat.load` | Loads raw files into `warehouse/hexstrat.duckdb`, schema `raw` |
| `stg_*` (dbt) | Typed staging views over raw tables; `stg_moves` also cleans faulty input (see Data quality) |
| `int_node_features` (dbt) | Per game and node: total pips, distinct resources, pips per resource, port |
| `fct_opening_placements` (dbt) | One row per opening settlement in finished games, with its features and `won` |
| `hexstrat.scorer` | Smoothed win rate by (pips, distinct resources); train/test split by `game_id` |
| `hexstrat.bot` | Picks the best-scoring opening spot, plays randomly afterwards |

The bot computes node features in Python (`hexstrat/features.py`) while training data computes them in SQL; `tests/test_features.py` runs dbt and checks both agree.

### Results (1,000 training games, seed 42)

- Spot quality predicts winning: players whose opening spot touches 13+ pips won 52% of games; spots touching no numbers won 8%.
- Scorer on 182 held-out games: AUC 0.69, log loss 0.523 vs 0.562 for always predicting 25%.
- Bot vs 3 random bots: **47.4% win rate** (95% CI 45.2–49.5%, 2,000 games).
- Same-seat control: a random player in the bot's seat, with the same game seeds, won 24.8% (95% CI 23.0–26.8%, 1,998 finished games). The bot differs from it only in its two opening settlements, so the gap comes from placement.
- Bot vs 3 weighted-random bots: 23.8% (95% CI 22.0–25.7%), no better than chance. Good openings don't make up for random play afterwards.

Simulation is seeded, but bot moves after the opening use Python's unseeded global RNG, so evaluation results vary slightly between runs (an earlier run gave 48.4% vs random bots).

## Data quality

To check that the pipeline survives messy input, `hexstrat.inject_faults` damages a copy of a run's raw files and logs every fault it injects. The damaged copy goes through the same load and dbt steps into a second warehouse, and `notebooks/fault_report.ipynb` checks the result against the clean warehouse, using the fault log as ground truth.

```bash
.venv/bin/python -m hexstrat.inject_faults --run-id <run_id> --seed 42           # -> data/raw_faulty
cp data/raw/board_*_<run_id>.parquet data/raw/run_<run_id>.json data/raw_faulty/
.venv/bin/python -m hexstrat.load --src data/raw_faulty --db warehouse/hexstrat_faulty.duckdb
(cd dbt && HEXSTRAT_DB=../warehouse/hexstrat_faulty.duckdb ../.venv/bin/dbt build)
```

### Faults injected (10,000-game run, seed 42)

| Fault | Count | How |
| --- | --- | --- |
| Duplicate rows | 42,239 | 0.5% of move rows copied and appended |
| Missing values | 42,450 | One cell blanked in 0.5% of rows, spread over `game_id`, `move_index`, `player`, `action_type`, `points` and the five `res_*` columns |

The fault log has one row per fault: type, table, `game_id`, `move_index`, column, original value, new value and seed. The same seed reproduces the same damage.

### Detection

The original tests caught only nulls in `game_id`, `player` and `action_type`: 12,573 of 84,689 faults (15%). No test checked that a move appears once per game, so all 42,239 duplicates went unnoticed. Adding a uniqueness test on `(game_id, move_index)` and `not_null` tests on the other blanked columns made every fault type fail on the damaged warehouse while all tests still pass on the clean one.

### Cleaning in `stg_moves`

| Problem | Handling |
| --- | --- |
| Null `game_id` or `move_index` | Row dropped: it can't be placed in a game |
| Duplicate `(game_id, move_index)` | One row kept, preferring the copy with no blanked values |
| Null `player` | Filled from the same seat in the same game |
| Null `points`, `res_*` | Forward-filled from the same player's previous move; 0 on a first move |
| Null `action_type` | Set to `UNKNOWN` |

Row counts reconcile exactly with the fault log. Staging removed 50,640 rows (8,490,046 raw → 8,439,406): 42,239 duplicates plus 8,486 rows with a null key, minus 85 duplicates whose copy also had a null key. The 8,401 dropped real moves are 0.1% of the clean data.

### Fill accuracy

Share of filled cells that match the original value:

| Column | Accuracy |
| --- | --- |
| `player` | 100% |
| `points` | 97.8% |
| `res_ore` | 83.3% |
| `res_brick` | 83.2% |
| `res_sheep` | 79.7% |
| `res_wheat` | 79.4% |
| `res_wood` | 78.5% |

Seat-to-colour is fixed within a game, so `player` is exact. Points change only when a player builds, so forward-filling them is nearly always right. Resource counts change between a player's own moves (dice income, the robber, discards), so about one forward-filled resource value in five is wrong. That noise touches only the 0.25% of rows that had a resource blanked.

### What was accepted

128 player-games are missing one of their two opening settlements, because that move's `action_type` became `UNKNOWN` or its key was null and the row was dropped. No player lost both. `two_opening_settlements_per_player` reports them as a warning rather than an error. The damaged warehouse builds with 25 passing tests and that 1 warning; the clean warehouse passes all 26.

### Impact on results

Win rate by colour in `fct_opening_placements`:

| Player | Clean | Damaged, after cleaning |
| --- | --- | --- |
| BLUE (weighted random) | 44.29% | 44.29% |
| RED | 18.80% | 18.79% |
| ORANGE | 18.75% | 18.75% |
| WHITE | 18.15% | 18.15% |

Every difference is under 0.01 percentage points, so conclusions drawn from the cleaned data match the clean data.
