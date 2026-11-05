-- One row per opening settlement: who placed it, where, what the spot produces, and whether they won.
with opening as (
    select
        game_id,
        player,
        seat,
        move_index,
        cast(action_value as integer) as node_id,
        won,
        row_number() over (partition by game_id, player order by move_index) as placement_number
    from {{ ref('stg_moves') }}
    where is_initial_build
      and action_type = 'BUILD_SETTLEMENT'
      and game_finished
)

select
    o.game_id,
    o.player,
    o.seat,
    o.placement_number,
    o.node_id,
    f.pips,
    f.n_resources,
    f.pips_wood,
    f.pips_brick,
    f.pips_sheep,
    f.pips_wheat,
    f.pips_ore,
    f.port_resource,
    o.won
from opening o
join {{ ref('int_node_features') }} f using (game_id, node_id)
