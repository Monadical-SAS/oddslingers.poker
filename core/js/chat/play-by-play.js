import React from 'react'
import {reduxify} from '@/util/reduxify'

import {chipAmtStr, formatStr} from "@/util/javascript"
import {localStorageGet} from '@/util/browser'
import {colorizeChatMessage} from '@/chat/components'
import {
    getGamestate,
    getActivePlayers,
    getLoggedInPlayer,
    getLastPlayerActed
} from '@/poker/selectors'

const PLAY_BY_PLAY = {
    NO_PLAYERS: "Not enough players to start a game",

    SITTING_OUT: "Sitting out. Check an option to join the game",
    SIT_IN_PENDING: "Waiting for next valid hand to sit in",
    SIT_IN_AT_BLINDS_PENDING: "Waiting for big blind to sit in",
    SIT_OUT_NEXT_HAND: "You will sit out at the end of the hand",
    SIT_OUT_AT_BLINDS: "You will sit out at next blind",
    LEAVE_SEAT_PENDING: "Leaving table at the end of hand...",
    NO_STACK: "You must buy chips to keep playing",
    REBUYING: "㆔{} chips are coming...",

    GO_ALLIN: "can go all-in or fold",
    CAN_CHECK: "can check or bet",
    CAN_CALL: "can call, raise or fold",
    FOLD: "folded",
}

const pbpArgs = (player, player_state) => {
    if (player_state == 'REBUYING') return [player.pending_rebuy]
    return []
}

const getPlayerState = (player) => {
    if (player){
        if (parseInt(player.stack.amt) <= parseInt(player.amt_to_call)) return 'GO_ALLIN'
        if (player.available_actions.includes('CHECK')) return 'CAN_CHECK'
        if (player.available_actions.includes('CALL')) return 'CAN_CALL'
        if (player.last_action == 'FOLD') return 'FOLD'
    }
    return null
}

const getLoggedInPlayerSittingOutState = (loggedin_player) => {
    if (loggedin_player){
        if (parseInt(loggedin_player.pending_rebuy) > 0) return 'REBUYING'
        if (loggedin_player.sitting_out && parseInt(loggedin_player.stack.amt) <= 0) return 'NO_STACK'
        if (loggedin_player.sitting_out) return loggedin_player.playing_state
        if (loggedin_player.playing_state == 'LEAVE_SEAT_PENDING') return 'LEAVE_SEAT_PENDING'
        if (loggedin_player.sit_out_next_hand) return 'SIT_OUT_NEXT_HAND'
        if (loggedin_player.sit_out_at_blinds) return 'SIT_OUT_AT_BLINDS'
    }
    return null
}

const msgForLastPlayer = (last_player) => {
    const action = last_player.last_action
    const bets = chipAmtStr(last_player.uncollected_bets.amt, true)
    if (action == 'POST') return `posted ${bets}`
    if (action == 'CHECK') return `checked`
    if (action == 'CALL') return `called ${bets}`
    if (action == 'BET') return `bet ${bets}`
    if (action == 'RAISE_TO') return `raised to ${bets}`
    return `just acted`
}

const getBetsInfo = (player, player_state) => {
    let call_info = ''
    if (['CAN_CALL', 'GO_ALLIN'].includes(player_state) && player.amt_to_call){
        const allin_msg = player_state == 'GO_ALLIN' ? ' (All-in)' : ''
        call_info = `${chipAmtStr(player.amt_to_call, true)} chips to call${allin_msg}. `
    }

    let bet_info = ''
    const checkcall_state = ['CAN_CHECK', 'CAN_CALL'].includes(player_state)

    if (checkcall_state && Number(player.min_bet) > 0){
        const min_bet = parseInt(player.min_bet)
        let move_type = 'raise'

        if (player_state == 'CAN_CHECK' && parseInt(player.uncollected_bets.amt) === 0) {
            move_type = 'bet'
        }
        if (min_bet > parseInt(player.stack.amt)){
            bet_info = `All-in to ${move_type}`
        } else {
            bet_info = `${chipAmtStr(player.min_bet, true)} chips to ${move_type}`
        }
    }
    return `${call_info}${bet_info}`
}

const getPlayerMovement = (player, player_state) => {
    let player_move = '...'
    if (player){
        const username = global.user && global.user.username == player.username ? "You" : player.username
        player_move = `${username} ${PLAY_BY_PLAY[player_state]}`
    }
    return player_move
}

const getLastPlayerMovement = (last_player) => {
    let last_player_move = ''
    if (last_player && last_player.last_action){
        const last_player_msg = msgForLastPlayer(last_player)
        const username = global.user && global.user.username == last_player.username ? "You" : last_player.username
        last_player_move = colorizeChatMessage(`${username} ${last_player_msg}`)
    }
    return last_player_move
}

const infoPlayByPlay = ({players, table}) => {
    const loggedin_player = getLoggedInPlayer(players)
    const loggedin_player_state = getLoggedInPlayerSittingOutState(loggedin_player)

    let last_player_move = ''
    let player_move = ''
    let bets_info = ''

    if (getActivePlayers(players).length < 2){
        player_move = PLAY_BY_PLAY['NO_PLAYERS']
    } else if (loggedin_player_state != null){
        const args = pbpArgs(loggedin_player, loggedin_player_state)
        player_move = formatStr(PLAY_BY_PLAY[loggedin_player_state], ...args)
    } else {
        const player_to_act = players[table.to_act_id]
        if (player_to_act && loggedin_player && player_to_act.id == loggedin_player.id){
            const player_state = getPlayerState(player_to_act)
            const last_player = getLastPlayerActed(players, table.to_act_id)
            last_player_move = getLastPlayerMovement(last_player)
            player_move = getPlayerMovement(player_to_act, player_state)
            bets_info = getBetsInfo(player_to_act, player_state)
        } else {
            player_move = player_to_act == null ? '...' : `${player_to_act.username}'s turn to act`
        }
    }

    return {last_player_move, player_move, bets_info}
}

export const PlayByPlay = reduxify({
    mapStateToProps: (state) => {
        const infoPBP = infoPlayByPlay(getGamestate(state))
        let show_playbyplay = true
        if (global.user) {
            show_playbyplay = global.user.show_playbyplay
        } else {
            const local_val = localStorageGet('show_playbyplay')
            show_playbyplay = local_val !== null ? local_val === "true" : true
        }

        return {show_playbyplay, ...infoPBP}
    },
    render({show_playbyplay, player_move, last_player_move, bets_info}){
        const show_panel = show_playbyplay
        return show_panel &&
            <div className="playbyplay-wrapper">
                <div className="playbyplay-content">
                    {last_player_move}<br/>
                    {player_move}<br/>
                    {bets_info}
                </div>
            </div>
    }
})
