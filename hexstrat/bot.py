"""A bot that picks opening settlements with the placement scorer and plays randomly otherwise.

Usage:
    python -m hexstrat.bot --games 2000 --opponents R --scorer artifacts/placement_scorer.json

Reports the bot's win rate with a 95% confidence interval. With 4 players, chance is 25%.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from catanatron import ActionType, Color, Game, Player, RandomPlayer
from catanatron.players.weighted_random import WeightedRandomPlayer

from hexstrat.features import node_features
from hexstrat.scorer import PlacementScorer

OPPONENTS = {"R": RandomPlayer, "W": WeightedRandomPlayer}


class PlacementBot(Player):
    def __init__(self, color: Color, scorer: PlacementScorer):
        super().__init__(color)
        self.scorer = scorer

    def decide(self, game, playable_actions):
        if game.state.is_initial_build_phase:
            settlements = [a for a in playable_actions if a.action_type == ActionType.BUILD_SETTLEMENT]
            if settlements:
                catan_map = game.state.board.map

                def score(action):
                    f = node_features(catan_map, action.value)
                    return self.scorer.score(f["pips"], f["n_resources"])

                return max(settlements, key=score)
        return random.choice(playable_actions)


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = wins / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def evaluate(scorer: PlacementScorer, games: int, opponent: str, seed: int) -> dict:
    rng = random.Random(seed)
    colors = [Color.RED, Color.BLUE, Color.WHITE, Color.ORANGE]
    wins = finished = 0
    for _ in range(games):
        players = [PlacementBot(colors[0], scorer)] + [OPPONENTS[opponent](c) for c in colors[1:]]
        winner = Game(players, seed=rng.randrange(2**31)).play()
        if winner is not None:
            finished += 1
            wins += winner == colors[0]
    low, high = wilson_interval(wins, finished)
    return {
        "opponents": f"3x {OPPONENTS[opponent].__name__}",
        "games_finished": finished,
        "bot_wins": wins,
        "win_rate": round(wins / finished, 4),
        "ci95": [round(low, 4), round(high, 4)],
        "chance": 0.25,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--games", type=int, default=2000)
    parser.add_argument("--opponents", choices=sorted(OPPONENTS), default="R")
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--scorer", type=Path, default=Path("artifacts/placement_scorer.json"))
    args = parser.parse_args()
    result = evaluate(PlacementScorer.load(args.scorer), args.games, args.opponents, args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
