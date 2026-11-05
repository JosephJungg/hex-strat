-- One row per move. Deduplication and type fixes for injected faults land here in weeks 5-7.
select
    run_id,
    game_id,
    cast(turn as integer)        as turn,
    cast(move_index as integer)  as move_index,
    player,
    cast(seat as integer)        as seat,
    action_type,
    action_value,
    is_initial_build,
    res_wood, res_brick, res_sheep, res_wheat, res_ore,
    settlements,
    cities,
    points,
    dev_cards,
    won,
    game_finished
from {{ source('raw', 'moves') }}
