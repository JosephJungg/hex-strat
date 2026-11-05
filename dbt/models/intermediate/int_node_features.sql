-- What a settlement on each node would produce, per game. Must match hexstrat.features.node_features,
-- which computes the same thing live for the bot (tests/test_features.py checks they agree).
with tiles as (
    select * from {{ ref('stg_board_tiles') }}
),

ports as (
    select game_id, node_id, max(port_resource) as port_resource
    from {{ ref('stg_board_ports') }}
    group by 1, 2
)

select
    t.game_id,
    t.node_id,
    sum(t.pips)                                                    as pips,
    count(distinct case when t.resource <> 'DESERT' then t.resource end) as n_resources,
    sum(case when t.resource = 'WOOD'  then t.pips else 0 end)     as pips_wood,
    sum(case when t.resource = 'BRICK' then t.pips else 0 end)     as pips_brick,
    sum(case when t.resource = 'SHEEP' then t.pips else 0 end)     as pips_sheep,
    sum(case when t.resource = 'WHEAT' then t.pips else 0 end)     as pips_wheat,
    sum(case when t.resource = 'ORE'   then t.pips else 0 end)     as pips_ore,
    p.port_resource
from tiles t
left join ports p using (game_id, node_id)
group by t.game_id, t.node_id, p.port_resource
