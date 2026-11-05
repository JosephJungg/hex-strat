-- Fails for any player in a finished game without exactly two opening settlements.
select game_id, player, count(*) as settlements
from {{ ref('fct_opening_placements') }}
group by game_id, player
having count(*) <> 2
