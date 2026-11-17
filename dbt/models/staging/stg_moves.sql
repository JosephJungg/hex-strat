with source as (
    select run_id,
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
    from {{ source('raw', 'moves')}}
),

drop_bad_keys as (
    select * from source
    where game_id is not null and move_index is not null
),

deduped as (
    select run_id,
        game_id,
        turn,
        move_index,
        player,
        seat,
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
        from (select *, row_number() over (partition by game_id, move_index order by points is null, player is null) as rowNum from drop_bad_keys)
        where rowNum = 1
),

filled as (
    select 
    run_id, 
    game_id,
    turn,
    move_index,
    coalesce(player, max(player) over (partition by game_id, seat)) as player, 
    seat,
    coalesce(action_type, 'UNKNOWN') as action_type,
    action_value,
    is_initial_build,
    coalesce(last_value(res_wood ignore nulls) over (partition by game_id, seat order by move_index), 0) as res_wood,
    coalesce(last_value(res_brick ignore nulls) over (partition by game_id, seat order by move_index), 0) as res_brick,
    coalesce(last_value(res_sheep ignore nulls) over (partition by game_id, seat order by move_index), 0) as res_sheep,
    coalesce(last_value(res_wheat ignore nulls) over (partition by game_id, seat order by move_index), 0) as res_wheat,
    coalesce(last_value(res_ore ignore nulls) over (partition by game_id, seat order by move_index), 0) as res_ore,
    settlements,
    cities,
    coalesce(last_value(points ignore nulls) over (partition by game_id, seat order by move_index), 0) as points,
    dev_cards,
    won,
    game_finished
    from deduped

)

select * from filled

