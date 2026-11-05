-- Fails for any finished game without exactly one winning player.
select game_id, count(distinct case when won then player end) as winners
from {{ ref('stg_moves') }}
where game_finished
group by game_id
having count(distinct case when won then player end) <> 1
