import {Become, Translate, Style, Opacity,
        Animate, AnimateCSS} from 'redux-time/node/animations'

import {flattened} from '@/util/javascript'
import {offset, center, styleFor, toCenter} from '@/poker/css'
import {SOUNDS_DURATION} from '@/constants'


// generate a gamestate path
const pathTo = (path) =>
    `/gamestate${path === undefined ? '' : path}`


export const PATCH = ({path, value, start_time}) => {
    return Become({
        path: pathTo(path),
        state: value,
        start_time,
    })
}

export const PATCHES = ({patches, start_time}) => {
    return (patches || []).map(({path, value}) =>
        PATCH({path, value, start_time})
    )
}

export const TIMED_PATCHES = ({patches, start_times}) => {
    const get_start_time = (path, start_time_dict) => {
        for (let key of Object.keys(start_time_dict)) {
            if (path.includes(key)) {         // TODO: make this more precise
                return start_time_dict[key]
            }
        }
        throw `No start time provided for path '${path}'`
    }

    return (patches || []).map(({path, value}) =>
        PATCH({
            path,
            value,
            start_time: get_start_time(path, start_times),
        })
    )
}

export const SNAPTO = ({gamestate, start_time}) => {
    // console.log({gamestate, start_time})
    return [
        Become({
            path: pathTo(''),
            state: gamestate,
            start_time,
        })
    ]
}

export const PROGRESS = ({player_id, start_time, duration}) => {
    return [
        Become({
            path: pathTo(`/table/to_act_id`),
            state: player_id,
            start_time
        }),
        Animate({
            path: pathTo(`/players/${player_id}/seconds_remaining`),
            start_time,
            duration,
            start_state: duration/1000,
            end_state: 0,
        }),
    ]
}

export const HIDE_PROGRESSBAR = ({start_time}) => {
    return Become({
        path: pathTo(`/table/to_act_id`),
        state: null,
        start_time
    })
}

export const DEAL_PLAYER = ({player_id, idx, card, start_time, patches, duration=150}) => {
    const path = pathTo(`/players/${player_id}/cards/${idx}`)
    if (typeof(card) !== 'string') {
        debugger
    }

    return [
        Become({path: path + '/card', start_time, state: card}),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: 'deal_player',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION['deal_player'],
            state: '',
        }),
        Translate({
            path,
            start_time,
            duration,
            start_state: {top: -4, left: 0},
            end_state: {top: 0, left: 0},
            unit: 'px',
        }),
        Opacity({
            path,
            start_state: 0,
            end_state: 1,
            start_time,
            duration: duration/2,
        }),
        ...PATCHES({patches, start_time: start_time + duration + 1})
    ]
}

export const DEAL_BOARD = ({idx, card, start_time, patches, duration=300}) => {
    const path = pathTo(`/table/board/${idx}`)
    return [
        Become({path: path + '/card', start_time, state: card}),
        Opacity({
            path,
            start_state: 0,
            end_state: 1,
            start_time,
            duration: duration/2,
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: 'deal_board',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION['deal_board'],
            state: '',
        }),
        AnimateCSS({path, name: "flipInY", start_time, duration}),
        ...PATCHES({patches, start_time: start_time + duration + 1}),
    ]
}

export const WIN = ({pot_id, amt, player_id, winning_hand=null,
                     start_time=null, patches=null, css, duration=2000}) => {

    const pot_path = pathTo(`/table/sidepot_summary/${pot_id}`)
    const chips_path = pathTo(`/players/${player_id}/uncollected_bets`)

    const start_state = offset(styleFor(css, '/table/sidepot_summary'))
    const end_state = offset(styleFor(css, `/players/${player_id}/uncollected_bets`))

    const move_dur = duration * 0.75
    const fade_dur = duration - move_dur

    const card_anims = (winning_hand || []).map(card => {
        const cardpath = pathTo(card.path)
        return [
            Become({
                path: cardpath + '/style',
                state: {
                    'opacity': '1',
                    'marginTop': '-4px',
                },
                start_time,
            }),
            Become({
                path: cardpath + '/style',
                state: {},
                start_time: start_time + duration,
            }),
        ]
    })

    return [
        Become({
            path: pathTo('/table/className'),
            state: winning_hand ? 'table-showdown' : '',
            start_time,
        }),
        Become({
            path: pathTo('/table/badge_ready'),
            state: true,
            start_time: start_time + move_dur,
        }),
        Become({
            path: pathTo('/table/level_notifications_ready'),
            state: true,
            start_time: start_time + move_dur,
        }),
        ...flattened(card_anims),
        Become({
            path: chips_path + '/amt',
            state: Number(amt),
            start_time,
        }),
        Become({
            path: pot_path,
            state: {amt: 0},
            start_time,
        }),
        Become({
            path: chips_path + '/style',
            state: {opacity: 1},
            start_time,
        }),
        Become({
            path: pathTo(`/players/${player_id}/winner`),
            state: true,
            start_time: start_time - 1
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: 'win',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION['win'],
            state: '',
        }),
        Become({
            path: pathTo(`/players/${player_id}/winner`),
            state: false,
            start_time: start_time + SOUNDS_DURATION['win']
        }),
        Style({
            path: chips_path,
            start_time,
            duration: move_dur,
            start_state,
            end_state,
            unit: 'px',
            curve: 'easeOutQuart',
        }),
        Opacity({
            path: chips_path,
            start_time: start_time + move_dur,
            duration: fade_dur,
            start_state: 1,
            end_state: 0,
            curve: 'easeOutQuad',
        }),
        Become({
            path: chips_path + '/style',
            state: {opacity: 0},
            start_time: start_time + move_dur,
        }),
        Become({
            path: pathTo('/table/className'),
            state: '',
            start_time: start_time + move_dur,
        }),
        Become({
            path: pathTo('/table/between_hands'),
            start_time,
            state: true,
        }),
        ...PATCHES({patches, start_time: start_time + move_dur}),
    ]
}

export const POST = ({player_id, start_time=null, amt, patches=null, duration=1000}) => {
    const player_path = pathTo(`/players/${player_id}`)
    const table_path = pathTo(`/table`)
    return [
        Become({
            path: table_path + '/notifications_ready',
            start_time,
            state: true,
        }),
        Become({
            path: table_path + '/animation_ends',
            start_time,
            state: true,
        }),
        Become({
            path: player_path + '/last_action',
            start_time,
            state: 'POST',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: 'bet',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION['bet'],
            state: '',
        }),
        Become({
            path: player_path + '/uncollected_bets',
            start_time,
            state: {amt},
        }),
        Translate({
            path: player_path + '/uncollected_bets',
            start_time,
            duration: 500,
            start_state: {top: 0, left: 0},
            end_state: {top: -10, left: 0},
            unit: 'px',
            curve: 'easeOutQuart'
        }),
        Translate({
            path: player_path + '/uncollected_bets',
            start_time: start_time + 500,
            start_state: {top: -10, left: 0},
            end_state: {top: 0, left: 0},
            duration: 500,
            unit: 'px',
            curve: 'easeOutQuart',
        }),
        ...TIMED_PATCHES({patches,
            start_times: {
                '/total_pot': start_time + 1,
                '/stack/amt': start_time + 1,
                '/last_action': start_time + 1,
                '/uncollected_bets/amt': start_time + duration + 1,
            }
        }),
    ]
}

export const DISCARD_CARDS = ({player_id, start_time=null, css,
                               duration=1000}) => {

    const cards_path = pathTo(`/players/${player_id}/cards`)
    const cards_css = styleFor(css, `/players/${player_id}/cards`)
    return [
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: 'fold',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION['fold'],
            state: '',
        }),
        Style({
            path: cards_path,
            start_time,
            duration: 1000,
            start_state: offset(cards_css),
            end_state: center(styleFor(css, '/table'), cards_css),
            unit: 'px',
            curve: 'easeOutQuart',
        }),
        Opacity({
            path: cards_path,
            start_time,
            duration,
            start_state: 1,
            end_state: 0,
            curve: 'easeInQuad',
        }),
    ]
}

export const MUCK = ({player_id, start_time=null, patches=null, css,
                      duration=1000}) => {
    return [
        ...DISCARD_CARDS({player_id, start_time, css, duration}),
        ...PATCHES({patches, start_time: start_time + duration + 1}),
    ]
}

export const FOLD = ({player_id, start_time=null, cards=null, patches=null, css, duration=1000}) => {
    const player_path = pathTo(`/players/${player_id}`)
    let cards_duration = 0
    if (cards.length) {
        cards_duration = 800
    }
    return [
        Become({
            path: player_path + '/last_action',
            start_time: start_time,
            state: 'FOLD',
        }),
        ...REVEAL_HAND({player_id, cards, start_time, duration: 800}),
        ...DISCARD_CARDS({player_id, start_time: start_time + cards_duration, css, duration}),
        ...TIMED_PATCHES({patches,
            start_times: {
                '/last_action': start_time + cards_duration + 1,
                '/cards': start_time + cards_duration + duration + 1,
            }
        }),
        HIDE_PROGRESSBAR({start_time})
    ]
}

export const CHECK = ({player_id, start_time=null, patches=null, duration=500}) => {
    const path = pathTo(`/players/${player_id}`)
    const half = duration / 6
    return [
        Become({
            path: path + '/last_action',
            start_time,
            state: 'CHECK',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: 'check',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION['check'],
            state: '',
        }),
        Opacity({
            path: path + '/cards',
            start_time,
            duration: half,
            start_state: 0,
            end_state: 1,
            curve: 'easeOutQuart',
        }),
        Opacity({
            path: path + '/cards',
            start_time: start_time + half,
            duration: half,
            start_state: 0,
            end_state: 1,
            curve: 'easeInQuad',
        }),
        ...PATCHES({patches, start_time: start_time + duration + 1}),
        HIDE_PROGRESSBAR({start_time}),
    ]
}

export const CALL = ({player_id, start_time=null, amt, all_in, patches=null, duration=500}) => {
    const path = pathTo(`/players/${player_id}`)
    const start_state = {top: 10, left: 0}
    const sound = all_in ? 'all_in' : 'bet'
    return [
        Become({
            path: path + '/last_action',
            start_time,
            state: 'CALL',
        }),
        Become({
            path: path + '/uncollected_bets/amt',
            start_time,
            state: Number(amt),
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: sound,
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION[sound],
            state: '',
        }),
        Become({
            path: pathTo('/table') + '/animation_ends',
            start_time,
            state: true,
        }),
        Translate({
            path: path + '/uncollected_bets',
            start_time,
            duration,
            start_state,
            end_state: {...start_state, top: start_state.top - 10},
            unit: 'px',
            curve: 'easeOutQuart',
        }),
        ...TIMED_PATCHES({patches,
            start_times: {
                '/total_pot': start_time + 1,
                '/stack/amt': start_time + 1,
                '/last_action': start_time + 1,
                '/uncollected_bets/amt': start_time + duration + 1,
            }
        }),
        HIDE_PROGRESSBAR({start_time})
    ]
}

export const BET = ({player_id, start_time=null, amt, all_in, patches=null, duration=500}) => {
    const path = pathTo(`/players/${player_id}`)
    const start_state = {top: 10, left: 0}
    const sound = all_in ? 'all_in' : 'bet'
    return [
        Become({
            path: path + '/last_action',
            start_time,
            state: 'BET',
        }),
        Become({
            path: path + '/uncollected_bets/amt',
            start_time,
            state: Number(amt),
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: sound,
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION[sound],
            state: '',
        }),
        Become({
            path: pathTo('/table') + '/animation_ends',
            start_time,
            state: true,
        }),
        Translate({
            path: path + '/uncollected_bets',
            start_time,
            duration,
            start_state,
            end_state: {...start_state, top: start_state.top - 10},
            unit: 'px',
            curve: 'easeOutQuart',
        }),
        ...TIMED_PATCHES({patches,
            start_times: {
                '/total_pot': start_time + 1,
                '/stack/amt': start_time + 1,
                '/last_action': start_time + 1,
                '/uncollected_bets/amt': start_time + duration + 1,
            }
        }),
        HIDE_PROGRESSBAR({start_time})
    ]
}

export const RAISE_TO = ({player_id, start_time=null, amt, all_in,
                          patches=null, duration=500}) => {
    const path = pathTo(`/players/${player_id}`)
    const start_state = {top: 10, left: 0}
    const sound = all_in ? 'all_in' : 'raise'
    return [
        Become({
            path: path + '/last_action',
            start_time,
            state: 'RAISE_TO',
        }),
        Become({
            path: path + '/uncollected_bets/amt',
            start_time,
            state: Number(amt),
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: sound,
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION[sound],
            state: '',
        }),
        Become({
            path: pathTo('/table') + '/animation_ends',
            start_time,
            state: true,
        }),
        Translate({
            path: path + '/uncollected_bets',
            start_time,
            duration,
            start_state,
            end_state: {...start_state, top: start_state.top - 10},
            unit: 'px',
            curve: 'easeOutQuart',
        }),
        ...TIMED_PATCHES({patches,
            start_times: {
                '/total_pot': start_time + 1,
                '/stack/amt': start_time + 1,
                '/last_action': start_time + 1,
                '/uncollected_bets/amt': start_time + duration + 1,
            }
        }),
        HIDE_PROGRESSBAR({start_time})
    ]
}

export const BOUNTY_WIN = ({player_id, cards, start_time, css, duration=1200}) => {

    const path = pathTo(`/players/${player_id}/cards/`)
    const flip_duration = (duration * 0.5) / cards.length
    const {bounty_font_style} = css.table
    const bounty_start_time = start_time + duration
    const rank_anim_duration = 1200

    const bounty_win_anims = cards.map((card, idx) => {
        const cardpath = `${path}${idx}`
        const start_flip = start_time + flip_duration * idx

        return [
            Become({
                path: `${cardpath}/card`,
                state: card,
                start_time: start_flip,
            }),
            AnimateCSS({
                path: cardpath,
                name: "flipInY",
                start_time: start_flip,
                duration: flip_duration,
            }),
            Style({
                path: `${path}rank_style`,
                start_time: bounty_start_time,
                duration: rank_anim_duration,
                start_state: {fontSize: 32},
                end_state: {fontSize: bounty_font_style.fontSize},
                curve: 'linear',
                unit: 'px'
            }),
            Become({
                path: `${path}rank_style/style`,
                start_time: bounty_start_time,
                state: {
                    ...bounty_font_style,
                    color: 'orange',
                    position: 'absolute'
                }
            }),
            Become({
                path: pathTo('/table') + '/sound',
                start_time: bounty_start_time,
                state: 'bounty',
            }),
            Become({
                path: pathTo('/table') + '/sound',
                start_time: bounty_start_time + SOUNDS_DURATION['bounty'],
                state: '',
            }),
        ]
    })

    return [
        ...flattened(bounty_win_anims)
    ]
}

export const REVEAL_HAND = ({player_id, cards, start_time, patches=null,
                             duration=1200}) => {

    const path = pathTo(`/players/${player_id}/cards/`)
    const flip_duration = (duration * 0.5) / cards.length

    const card_anims = cards.map((card, idx) => {
        const cardpath = `${path}${idx}`
        const start_flip = start_time + flip_duration * idx
        return [
            Become({
                path: `${cardpath}/card`,
                state: card,
                start_time: start_flip,
            }),
            Become({
                path: pathTo('/table') + '/sound',
                start_time,
                state: 'reveal_hand',
            }),
            Become({
                path: pathTo('/table') + '/sound',
                start_time: start_time + SOUNDS_DURATION['reveal_hand'],
                state: '',
            }),
            Become({
                path: pathTo('/table') + '/sound',
                start_time: start_time + SOUNDS_DURATION['reveal_hand'],
                state: '',
            }),
            Opacity({
                path: cardpath,
                start_state: 0,
                end_state: 1,
                start_time: start_flip,
                duration: flip_duration,
            }),
            AnimateCSS({
                path: cardpath,
                name: "flipInY",
                start_time: start_flip,
                duration: flip_duration,
            }),
        ]
    })
    return [
        ...flattened(card_anims),
        ...PATCHES({patches, start_time: start_time + duration + 1}),
    ]
}


export const NEW_STREET = ({player_chips, start_time, patches, css,
                            duration=500}) => {
    const chip_movements = player_chips.map((path) => {
        const player_id = path.split('players/')[1].split('/')[0]
        if (!player_id) debugger

        return Style({
            path: pathTo(path),
            start_state: offset(styleFor(css, `/players/${player_id}/uncollected_bets`)),
            end_state: offset(styleFor(css, '/table/sidepot_summary')),
            start_time,
            duration,
            curve: 'linear',
            unit: 'px',
        })
    })

    return [
        Become({
            path: pathTo('/table') + '/sound',
            start_time,
            state: 'return_chips',
        }),
        Become({
            path: pathTo('/table') + '/sound',
            start_time: start_time + SOUNDS_DURATION['return_chips'],
            state: '',
        }),
        ...flattened(chip_movements),
        ...TIMED_PATCHES({
                patches,
                start_times: {
                    '/last_action': start_time + 1,
                    '/sidepot_summary': start_time + duration + 1,
                    '/uncollected_bets/amt': start_time + duration,
            }
        }),
        HIDE_PROGRESSBAR({start_time}),
    ]
}

export const RETURN_CHIPS = ({player_id, start_time=null, amt,
                          patches=null, duration=500, css}) => {
    const path = pathTo(`/players/${player_id}`)

    const bets_style = styleFor(css, `/players/${player_id}/uncollected_bets`)
    const player_style = styleFor(css, `/players/${player_id}`)

    const start_state = offset(bets_style)
    const end_state = toCenter(player_style, bets_style)

    return [
        Become({
            path: path + '/uncollected_bets/amt',
            start_time,
            state: Number(amt),
        }),
        Style({
            path: path + '/uncollected_bets',
            start_time,
            duration,
            start_state,
            end_state,
            unit: 'px',
            curve: 'easeOutQuart',
        }),
        ...TIMED_PATCHES({
            patches,
            start_times: {
                '/stack/amt': start_time + 1,
                '/uncollected_bets/amt': start_time + duration + 1,
            }
        })
    ]
}

export const frontend_anims_from_backend_anim = (anim_start_time,
                                                 animation, css) => {
    if (animation.type == 'SNAPTO') {
        return SNAPTO({
            gamestate: animation.value,
            start_time: anim_start_time,
        })
    }
    else if (animation.type == 'SET_BLIND_POS') {
        return PATCHES({
            patches: animation.patches,
            start_time: anim_start_time,
            css,
        })
    }
    else if (animation.type == 'ANTE') {
        // TODO
        return []
    }
    else if (animation.type == 'POST') {
        return POST({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            amt: Number(animation.value.amt),
            css,
        })
    }
    else if (animation.type == 'POST_DEAD') {
        return POST({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            amt: Number(animation.value.amt),
            css,
        })
    }
    else if (animation.type == 'DEAL_PLAYER') {
        return DEAL_PLAYER({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            card: animation.value.card,
            idx: animation.value.idx,
            css,
        })
    }
    else if (animation.type == 'DEAL_BOARD') {
        return DEAL_BOARD({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            card: animation.value.card,
            idx: animation.value.idx,
            css,
        })
    }
    else if (animation.type == 'BET') {
        return BET({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            amt: Number(animation.value.amt),
            all_in: animation.value.all_in,
            css,
        })
    }
    else if (animation.type == 'RAISE_TO') {
        return RAISE_TO({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            amt: Number(animation.value.amt),
            all_in: animation.value.all_in,
            css,
        })
    }
    else if (animation.type == 'CALL') {
        return CALL({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            amt: Number(animation.value.amt),
            all_in: animation.value.all_in,
            css,
        })
    }
    else if (animation.type == 'CHECK') {
        return CHECK({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            css,
        })
    }
    else if (animation.type == 'FOLD') {
        return FOLD({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            cards: animation.value,
            css,
        })
    }
    else if (animation.type == 'NEW_STREET') {
        return NEW_STREET({
            start_time: anim_start_time,
            player_chips: animation.value,
            patches: animation.patches,
            css,
        })
    }
    else if (animation.type == 'RESET') {
        return PATCHES({
            patches: animation.patches,
            start_time: anim_start_time
        })
    }
    else if (animation.type == 'WIN') {
        return WIN({
            start_time: anim_start_time,
            pot_id: animation.value.pot_id,
            amt: animation.value.amt,
            player_id: animation.subj.id,
            patches: animation.patches,
            winning_hand: animation.value.winning_hand,
            css,
        })
    }
    else if (animation.type == 'RETURN_CHIPS') {
        return RETURN_CHIPS({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            amt: Number(animation.value.amt),
            css,
        })
    }
    else if (animation.type == 'REVEAL_HAND') {
        return REVEAL_HAND({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            cards: animation.value,
            patches: animation.patches
        })
    }
    else if (animation.type == 'MUCK') {
        return MUCK({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            patches: animation.patches,
            css,
        })
    }
    else if (animation.type == 'BOUNTY_WIN') {
        return BOUNTY_WIN({
            player_id: animation.subj.id,
            start_time: anim_start_time,
            cards: animation.value,
            css
        })
    }
    else if (animation.type == 'TAKE_SEAT') {
        // TODO
        return []
    }
    else if (animation.type == 'LEAVE_SEAT') {
        // TODO
        return []
    }
    else if (animation.type == 'SIT_IN') {
        // TODO
        return []
    }
    else if (animation.type == 'SIT_OUT') {
        // TODO
        return []
    }
    else if (animation.type == 'UPDATE_STACK') {
        // TODO
        return []
    }
    else if (animation.type == 'SET_LEAVING_TABLE') {
        // TODO
        return []
    }
    return []
}

export const anim_delay = (type) => {
    const delays = {
        'SNAPTO': 0,
        // 'NEW_HAND': 200,
        // 'SET_BLIND_POS': 100,
        // 'ANTE': 100,
        'POST': 100,
        'POST_DEAD': 100,
        'DEAL_PLAYER': 80,
        'DEAL_BOARD': 200,

        'BET': 500,
        'RAISE_TO': 500,
        'CALL': 500,
        'CHECK': 500,
        'FOLD': 1000,

        'NEW_STREET': 750,
        'WIN': 1500,
        'RETURN_CHIPS': 400,
        'REVEAL_HAND': 1200,
        'MUCK': 400,
        'BOUNTY_WIN': 2400,

        // 'TAKE_SEAT': 500,
        // 'LEAVE_SEAT': 500,
        // 'SIT_IN': 500,
        // 'SIT_OUT': 500,
        // 'UPDATE_STACK': 500,
        // 'SET_LEAVING_TABLE': 500,
    }
    return delays[type] === undefined ? 0 : delays[type]
}
