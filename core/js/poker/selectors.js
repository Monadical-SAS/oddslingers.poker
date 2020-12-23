import {rotated} from '@/util/javascript'

export const getGamestate = (state) =>
    state.animations.state.gamestate

export const getOrderedPlayerIds = (players) => {
    let player_ids = [...Object.keys(players)].sort((a, b) =>
        players[a].position - players[b].position)

    // If there are players and one of them is the current player
    if (player_ids.length && player_ids.some(id => players[id].logged_in)) {
        // Rotate players until the current player is in first position
        while (!(players[player_ids[0]] || {}).logged_in) {
            player_ids = rotated(player_ids, 1)
        }
    }
    return player_ids
}

export const playerIdsByActionOrder = (players, to_act_id) => {
    let player_ids = Object.keys(players).sort((a, b) =>
        players[a].position - players[b].position)

    if (!player_ids.includes(to_act_id)) return null

    while (player_ids[0] != to_act_id) {
        player_ids = rotated(player_ids)
    }
    return player_ids
}

export const getLoggedInPlayerId = (players) => {
    if (!players) return null
    const logged_in_player_ids = Object.keys(players).filter(
        player_id => players[player_id].logged_in
    )
    if (logged_in_player_ids.length == 0) {
        return null
    }
    else if (logged_in_player_ids.length > 1) {
        throw 'More than one player is logged in frontend.'
    }
    else if (logged_in_player_ids.length == 1) {
        const logged_in_player = players[logged_in_player_ids[0]]
        if (global.username && (logged_in_player.username != global.user.username)) {
            throw "Current player's name does not equal logged in user's username"
        }
        return logged_in_player_ids[0]
    }
}

export const getLoggedInPlayer = (players) => {
    const logged_in_player_id = getLoggedInPlayerId(players)
    if (logged_in_player_id === null) {
        return null
    }
    return players[logged_in_player_id]
}

export const getPlayersByPosition = (players) => {
    const player_ids = getOrderedPlayerIds(players)
    return player_ids.reduce((obj, player_id) => {
        const player = players[player_id]
        obj[player.position] = player
        return obj
    }, {})
}

export const getSatPlayers = (players) =>
    Object.values(players).filter(player => !player.sitting_out)

export const getActivePlayers = (players) =>
    Object.values(players).filter(player => player.is_active)


export const getPlayerBuyin = (table_min_buyin, last_stack) =>
    last_stack > table_min_buyin ? last_stack : table_min_buyin


export const getLastUserChatLine = (chat_lines, username) => {
    const last_line = chat_lines.filter(line => line.speaker == username).slice(-1)[0]
    return last_line || null
}


export const getLastPlayerActed = (players, to_act_id) => {
    const acting_ids = playerIdsByActionOrder(players, to_act_id)
    const plyr_id_before = (acting_ids || []).filter(p_id => {
        return (
            players[p_id].last_action != null
            && players[p_id].last_action != 'FOLD'
            && players[p_id].is_active
        )
    }).slice(-1)[0]
    return players[plyr_id_before]
}


// Reselect.js Selector Example:

/*
import {createSelector} from 'reselect'

const getVisibilityFilter = (state, props) =>
    state.todoLists[props.listId].visibilityFilter

const getTodos = (state, props) => state.todoLists[props.listId].todos

const getVisibleTodos = createSelector(
    [getVisibilityFilter, getTodos],
    (visibilityFilter, todos) => {
    switch (visibilityFilter) {
        case 'SHOW_COMPLETED':
            return todos.filter(todo => todo.completed)
        case 'SHOW_ACTIVE':
            return todos.filter(todo => !todo.completed)
        default:
            return todos
    }
  }
)

export default getVisibleTodos
*/
