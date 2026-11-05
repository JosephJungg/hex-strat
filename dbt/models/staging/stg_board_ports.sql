select
    game_id,
    node_id,
    port_resource
from {{ source('raw', 'board_ports') }}
