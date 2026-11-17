select game_id, move_index, count(*) as dups from {{ ref('stg_moves')}}
where game_id is not null and move_index is not null
GROUP BY game_id, move_index
having dups > 1