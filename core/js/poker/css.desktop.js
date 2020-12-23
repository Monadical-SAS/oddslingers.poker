import {mapObj} from '@/util/javascript'
import {getCSS} from '@/util/css.js'
import {is_portrait} from '@/util/browser'

import {
    btn_positions_desktop_landscape,
    btn_positions_desktop_portrait
} from '@/constants'

import {
    ellipse_positions,
    center,
    ellipse_offset,
    getPlayerPosition,
    styleForWithUnits,
    getBtnPosition
} from '@/poker/css'

// stub document to null in node.js so we dont try and fetch document properties
var document = document || null

// make sure CSS values match values defined in JS get_table_size()
if (document) {
    if (getCSS(document.styleSheets, '.table', 'width')
            != `${get_table_size().width}px` ||
        getCSS(document.styleSheets, '.table', 'height')
            != `${get_table_size().height}px`)
    throw 'get_table_size() constants must match the height & width defined in base.css: .table!'
}

const get_table_size = () => {
    return {
        width: 1120,   // px
        height: 740,  // px
    }
}

const get_players_offset = () =>
    is_portrait() ? 180 : -70

const get_player_style = (player, players, player_coords, num_seats,
                          seatbox_height, seatbox_width) => {
    const player_position = getPlayerPosition(player.position, players, num_seats)
    return {
        ...player_coords[player_position],
        width: (196 || seatbox_height),
        height: (126 || seatbox_width),
        top : player_coords[player_position].top + (
            get_players_offset()
        ),
        left: player_coords[player_position].left - (
            98
        ),
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

    const height_btn_offset = is_portrait() ? 80 : 0
    const num_seats = Number(table.num_seats)

    const player_coords = ellipse_positions(
        num_seats, table_center, 0.80, ellipse_offset(0), 50
    )
    const wager_coords = ellipse_positions(
        num_seats, table_center, 0.53, ellipse_offset(-40), 40
    )
    const btn_position = getPlayerPosition(
        table.btn_idx, players, num_seats
    )
    const btn_positions_desktop = is_portrait() ?
                                 btn_positions_desktop_portrait
                                 : btn_positions_desktop_landscape
    const btn_coord = getBtnPosition(
        num_seats, table_center, 0.58, btn_positions_desktop,
        ellipse_offset(height_btn_offset), 50, btn_position
    )
    const card_coords = player_coords.map(({left, top}) => ({
        left: left - 80,
        top: top + 85 + get_players_offset(),
    }))

    const seatbox_width = get_table_size().width * 0.1875
    const seatbox_height = seatbox_width * 0.6333

    const css_obj = {
        table: {
            style: {
                top: 0,
                left: 0,
                width: felt.width,
                height: felt.height + (
                    is_portrait() ? 500 : 0
                ),
            },
            btn: {
                style: {
                    width: 28,
                    height: 28,
                    top: btn_coord.top + (
                        is_portrait() ? 260 : 0
                    ),
                    left: btn_coord.left - 14,
                }
            },
            board: {
                style: {
                    width: 560,
                    height: 280,
                    top: 252 + (
                        is_portrait() ? 421 : 0
                    ),
                    left: 150,
                }
            },
            sidepot_summary: {
                style: {
                    top: 413 + (
                        is_portrait() ? 280 : -30
                    ),
                    left: (felt.width/2) - 40,
                    width: 350,
                    height: 196,
                }
            },
            bounty_font_style: {
                fontSize: 122,
                marginLeft: '-39px'
            }
        },
        players: mapObj(players, (player_id, player) => ({
            style: get_player_style(player, players, player_coords, num_seats, seatbox_height, seatbox_width),
            uncollected_bets: {
                style: {
                    height: 'auto',
                    width: 'auto',
                    textAlign: 'center',
                    top : wager_coords[getPlayerPosition(player.position, players, num_seats)].top  + 45 + (
                        get_players_offset()
                    ),
                    left: wager_coords[getPlayerPosition(player.position, players, num_seats)].left - (
                        45
                    ),
                }
            },
            cards: {
                style: {
                    ...card_coords[getPlayerPosition(player.position, players, num_seats)],
                    width: 158,
                    height: 95,
                    position: 'absolute',
                    display: 'block',
                    textAlign: 'center',
                }
            }
        })),
        emptySeats: mapObj(card_coords, (position) =>
            get_player_style(
                {position},
                players,
                player_coords,
                num_seats,
                seatbox_height,
                seatbox_width,
            )
        ),
    }
    
    last_table = table
    last_players = players
    last_css_obj = css_obj
    return css_obj
}

export {styleForWithUnits}
