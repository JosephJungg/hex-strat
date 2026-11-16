    with filtered as (select
        game_id, 
        player, 
        seat,
        won,
        cast(action_value as integer) as node_id,
        row_number() over (partition by game_id, player order by move_index) as placement_number
        FROM {{ ref('stg_moves')}}
        WHERE game_finished and 
        action_type = 'BUILD_SETTLEMENT' and 
        is_initial_build
    )

    SELECT 
    f.game_id,
    f.node_id,
    f.player,
    f.seat, 
    f.won,
    f.placement_number,
    o.pips,
    o.n_resources,
    o.pips_wood,
    o.pips_brick, 
    o.pips_sheep,
    o.pips_ore,
    o.pips_wheat,
    o.port_resource
    FROM filtered f
    JOIN {{ ref('int_node_features')}} o using(game_id, node_id)