select
    game_id,
    node_id,
    tile_id,
    resource,
    number,
    -- "pips": how many of the 36 dice outcomes roll this number (6 and 8 = 5, 2 and 12 = 1)
    case when number is null then 0 else 6 - abs(7 - number) end as pips
from {{ source('raw', 'board_tiles') }}
