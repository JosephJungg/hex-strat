"""Node features computed live from a game's board, for the bot at decision time.

This must match dbt/models/intermediate/int_node_features.sql, which computes the same
features from the logged board for training. tests/test_features.py checks they agree.
"""

from __future__ import annotations

RESOURCES = ["WOOD", "BRICK", "SHEEP", "WHEAT", "ORE"]


def pips(number: int | None) -> int:
    """How many of the 36 dice outcomes roll this number (6 and 8 = 5, 2 and 12 = 1, desert = 0)."""
    return 0 if number is None else 6 - abs(7 - number)


def node_features(catan_map, node_id: int) -> dict:
    tiles = catan_map.adjacent_tiles[node_id]
    feats = {
        "pips": sum(pips(t.number) for t in tiles),
        "n_resources": len({t.resource for t in tiles if t.resource is not None}),
    }
    for r in RESOURCES:
        feats[f"pips_{r.lower()}"] = sum(pips(t.number) for t in tiles if t.resource == r)
    port = [res or "ANY" for res, nodes in catan_map.port_nodes.items() if node_id in nodes]
    feats["port_resource"] = max(port) if port else None
    return feats
