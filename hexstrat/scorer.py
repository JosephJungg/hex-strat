"""Trivial placement scorer: smoothed win rate by (pips, distinct resources), trained on fct_opening_placements.

Usage:
    python -m hexstrat.scorer --db warehouse/hexstrat.duckdb --out artifacts/placement_scorer.json

Train/test split is by game_id, never by row: both placements and all four players of a game
share one outcome, so a row-level split would leak the answer into the test set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import pandas as pd

PIPS_CAP = 13  # few spots exceed this; pool them
PRIOR_STRENGTH = 20  # pseudo-games pulling each cell toward its pips-only rate


def is_test_game(game_id: str, test_fraction: float = 0.2) -> bool:
    """Stable game-level split: the same game always lands on the same side."""
    bucket = int(hashlib.md5(game_id.encode()).hexdigest(), 16) % 1000
    return bucket < test_fraction * 1000


def _key(pips: int, n_resources: int) -> str:
    return f"{min(pips, PIPS_CAP)}|{n_resources}"


@dataclass
class PlacementScorer:
    table: dict[str, float]  # "pips|n_resources" -> win probability
    by_pips: dict[str, float]  # fallback for unseen combinations
    base_rate: float

    def score(self, pips: int, n_resources: int) -> float:
        return self.table.get(
            _key(pips, n_resources), self.by_pips.get(str(min(pips, PIPS_CAP)), self.base_rate)
        )

    @classmethod
    def fit(cls, df: pd.DataFrame) -> "PlacementScorer":
        df = df.assign(p=df["pips"].clip(upper=PIPS_CAP), won=df["won"].astype(int))
        base = df["won"].mean()
        pips_grp = df.groupby("p")["won"].agg(["sum", "count"])
        by_pips = ((pips_grp["sum"] + PRIOR_STRENGTH * base) / (pips_grp["count"] + PRIOR_STRENGTH)).to_dict()
        table = {}
        for (p, n), g in df.groupby(["p", "n_resources"])["won"]:
            prior = by_pips[p]
            table[_key(p, n)] = (g.sum() + PRIOR_STRENGTH * prior) / (len(g) + PRIOR_STRENGTH)
        return cls(table=table, by_pips={str(k): v for k, v in by_pips.items()}, base_rate=base)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "PlacementScorer":
        return cls(**json.loads(path.read_text()))


def auc(labels, scores) -> float:
    """Probability a random winner's placement scores above a random loser's (ties count half)."""
    df = pd.DataFrame({"y": labels, "s": scores})
    ranks = df["s"].rank()
    pos = df["y"].sum()
    neg = len(df) - pos
    return (ranks[df["y"] == 1].sum() - pos * (pos + 1) / 2) / (pos * neg)


def log_loss(labels, probs) -> float:
    eps = 1e-9
    return -sum(
        y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for y, p in zip(labels, probs)
    ) / len(labels)


def train(db: Path) -> tuple[PlacementScorer, dict]:
    with duckdb.connect(str(db), read_only=True) as con:
        df = con.sql("select game_id, pips, n_resources, won from marts.fct_opening_placements").df()
    test_mask = df["game_id"].map(is_test_game)
    train_df, test_df = df[~test_mask], df[test_mask]
    scorer = PlacementScorer.fit(train_df)

    y = test_df["won"].astype(int).tolist()
    preds = [scorer.score(p, n) for p, n in zip(test_df["pips"], test_df["n_resources"])]
    metrics = {
        "train_games": int(train_df["game_id"].nunique()),
        "test_games": int(test_df["game_id"].nunique()),
        "test_auc": round(auc(y, preds), 4),
        "test_log_loss": round(log_loss(y, preds), 4),
        "baseline_log_loss": round(log_loss(y, [scorer.base_rate] * len(y)), 4),
    }
    return scorer, metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path("warehouse/hexstrat.duckdb"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/placement_scorer.json"))
    args = parser.parse_args()
    scorer, metrics = train(args.db)
    scorer.save(args.out)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
