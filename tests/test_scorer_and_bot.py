import pandas as pd
from catanatron import Color, Game, RandomPlayer

from hexstrat.bot import PlacementBot, wilson_interval
from hexstrat.features import node_features
from hexstrat.scorer import PlacementScorer, auc, is_test_game


def test_split_is_by_game_and_stable():
    ids = [f"game-{i}" for i in range(2000)]
    first = [is_test_game(g) for g in ids]
    assert first == [is_test_game(g) for g in ids]
    assert 0.15 < sum(first) / len(ids) < 0.25


def test_scorer_prefers_better_spots():
    df = pd.DataFrame(
        {
            "pips": [2] * 50 + [12] * 50,
            "n_resources": [1] * 50 + [3] * 50,
            "won": [i < 5 for i in range(50)] + [i < 25 for i in range(50)],
        }
    )
    scorer = PlacementScorer.fit(df)
    assert scorer.score(12, 3) > scorer.score(2, 1)
    assert scorer.score(9, 2) > 0  # unseen combination falls back instead of failing


def test_auc():
    assert auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert auc([0, 1], [0.5, 0.5]) == 0.5


def test_bot_picks_highest_scoring_opening_spot():
    scorer = PlacementScorer(table={}, by_pips={str(p): p / 100 for p in range(14)}, base_rate=0.25)
    bot = PlacementBot(Color.RED, scorer)
    game = Game([bot] + [RandomPlayer(c) for c in (Color.BLUE, Color.WHITE, Color.ORANGE)], seed=5)
    while game.state.current_color() != Color.RED:
        game.play_tick()
    choice = bot.decide(game, game.state.playable_actions)
    best = max(
        node_features(game.state.board.map, a.value)["pips"]
        for a in game.state.playable_actions
    )
    assert node_features(game.state.board.map, choice.value)["pips"] == best


def test_wilson_interval_contains_rate():
    low, high = wilson_interval(500, 2000)
    assert low < 0.25 < high
