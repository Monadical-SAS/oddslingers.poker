import {mapObj} from '@/util/javascript'
import {
    is_portrait,
    getWindowWidth,
    getWindowHeight
} from '@/util/browser'

import {
    btn_positions_mobile_landscape,
    btn_positions_mobile_portrait,
    chips_positions_mobile_landscape,
    chips_positions_mobile_portrait
} from '@/constants'

import {
    ellipse_positions,
    center,
    getPlayerPosition,
    styleForWithUnits
} from '@/poker/css'


const get_table_size = () => {
    return {
        width: getWindowWidth(),   // px
        height: is_portrait() ?
                getWindowHeight() * 0.8
                : getWindowHeight(),  // px
    }
}

const get_player_style = (player_position, players, player_coords) => {
    return {
        ...player_coords[player_position],
        width: 85, // + (is_portrait() ? 140 : 40),
        height: 59, // + (is_portrait() ? 100 : 30),
        top : player_coords[player_position].top - (
            is_portrait() ? 41 : 31
        ),
        left: player_coords[player_position].left - 43,
    }
}

const getChipsPosition = (player_style, player_position, num_seats, coord_type) => {
    const chips_positions_mobile = is_portrait() ?
                                   chips_positions_mobile_portrait
                                   : chips_positions_mobile_landscape
    const player_coord = player_style[coord_type]
    const chips_offset = chips_positions_mobile[num_seats][player_position][coord_type]
    return player_coord + chips_offset
}

const getBtnPosition = (player_style, btn_position, num_seats) => {
    const btn_positions_mobile = is_portrait() ?
                                 btn_positions_mobile_portrait
                                 : btn_positions_mobile_landscape

    return {
        top: player_style['top'] + btn_positions_mobile[num_seats][btn_position]['top'],
        left: player_style['left'] + btn_positions_mobile[num_seats][btn_position]['left'],
    }
}

let last_table = null
let last_players = null
let last_css_obj = null
export const calculateTableCSS = ({table, players}, felt=null) => {
    if (table === last_table && players === last_players) {
        return last_css_obj
    }
    felt = felt || get_table_size()
    const table_center = center(felt)

    const num_seats = Number(table.num_seats)

    let width_player_offset = 10
    if (is_portrait()) {
        if (num_seats < 6) width_player_offset = -30
        else width_player_offset = -10
    }
    else if (num_seats < 6 ) width_player_offset = -30

    const height_player_offset = is_portrait() ? -31 : -23
    const player_coords = ellipse_positions(
        num_seats, table_center, 0.9, height_player_offset, width_player_offset
    )

    const btn_position = getPlayerPosition(
        table.btn_idx, players, num_seats
    )
    const player_style = get_player_style(btn_position, players, player_coords)

    const btn_coord = getBtnPosition(player_style, btn_position, num_seats)

    const card_coords = player_coords.map(({left, top}) => ({
        left: left - 44,
        top: top - (is_portrait() ? 28 : 17),
    }))

    const css_obj = {
        table: {
            style: {
                top: 0,
                left: 0,
                width: felt.width,
                height: felt.height,
            },
            btn: {
                style: {
                    top: btn_coord.top,
                    left: btn_coord.left,
                    width: 15,
                    height: 15,
                }
            },
            board: {
                style: {
                    width: 220,
                    height: 80,
                    top: (felt.height/2) - 40,
                    left: (felt.width/2) - 110,
                }
            },
            sidepot_summary: {
                style: {
                    top: (felt.height/2) + (
                        is_portrait() ? 15 : 20
                    ),
                    left: (felt.width/2) - 20,
                    width: 240,
                    height: 30,
                }
            },
            bounty_font_style: {
                fontSize: 42,
                marginLeft: -10
            }
        },
        players: mapObj(players, (player_id, player) => {
            const player_position = getPlayerPosition(player.position, players, num_seats)
            const player_style = get_player_style(player_position, players, player_coords)
            return {
                style: player_style,
                uncollected_bets: {
                    style: {
                        height: 'auto',
                        width: 'auto',
                        textAlign: 'center',
                        top : getChipsPosition(player_style, player_position, num_seats, 'top'),
                        left: getChipsPosition(player_style, player_position, num_seats, 'left'),
                    }
                },
                cards: {
                    style: {
                        ...card_coords[player_position],
                        width: 87,
                        height: 35,
                        position: 'absolute',
                        display: 'block',
                        textAlign: 'center',
                    }
                },
            }
        }),
        emptySeats: mapObj(player_coords, (position) => {
            const player_position = getPlayerPosition(position, players, num_seats)
            return get_player_style(
                player_position,
                players,
                player_coords,
            )
        }),
    }
    last_table = table
    last_players = players
    last_css_obj = css_obj
    return css_obj
}

export {styleForWithUnits}
