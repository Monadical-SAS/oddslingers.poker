import orderBy from 'lodash/orderBy'
import find from 'lodash/find'


/*************************** ACTIONS ******************************************/
export const onSubmitAction = (type, args) => ({
    type: 'SUBMIT_ACTION',
    action: {type, ...args}
})

/************************** REDUCERS ******************************************/
const initial_state = {
    id: '',
    name: '',
    tourney_path: '',
    table_path: '',
    tournament_status: null,
    game_variant: '',
    max_entrants: null,
    buyin_amt: null,
    entrants: [],
    user_funds: null,
    redirect_to_table: false,
    results: [],
    tournament_admin: null,
    presence: {},
    notifications: [],
    is_private: null,
}

export const tournament_summary = (state=initial_state, action) => {
    switch (action.type) {
        case 'UPDATE_TOURNAMENT_STATE': {
            return {
                ...state,
                id: action.id || state.id,
                name: action.name || state.name,
                tourney_path: action.tourney_path || state.tourney_path,
                table_path: action.table_path || state.table_path,
                tournament_status: action.tournament_status || state.tournament_status,
                game_variant: action.game_variant || state.game_variant,
                max_entrants: action.max_entrants || state.max_entrants,
                buyin_amt: action.buyin_amt || state.buyin_amt,
                entrants: action.entrants || state.entrants,
                user_funds: action.user_funds || state.user_funds,
                results: action.results || state.results,
                tournament_admin: action.tournament_admin || state.tournament_admin,
                presence: action.presence || state.presence,
                notifications: action.notifications || state.notifications,
                is_private: action.is_private || state.is_private,
                is_locked: action.is_locked || state.is_locked,
            }
        }
        case 'UPDATE_GAMESTATE': {
            const players_state = action.players || state.players
            const players = Object.values(players_state).map(player => ({
                username: player.username,
                stack: Number(player.stack.amt) + Number(player.uncollected_bets.amt)
            }))

            const updated_entrants = orderBy(state.entrants.map(entrant => {
                const player_entrant = find(players, {username: entrant.username})
                const new_props = player_entrant ?
                    {stack: player_entrant.stack, playing: true}
                    : {stack: 0, playing: false}

                return {
                    ...entrant,
                    ...new_props
                }
            }), 'stack', 'desc')

            return {
                ...state,
                entrants: updated_entrants
            }
        }
        case 'SUBMIT_ACTION': {
            const {type, ...args} = action.action
            setTimeout(
                () => window.page.socket.send_action(type, {...args || {}}),
                0
            )
            return state
        }
        case 'START_TOURNAMENT': {
            return {
                ...state,
                tournament_status: action.tournament_status,
                redirect_to_table: true,
                table_path: action.table_path
            }
        }
        case 'UPDATE_PRESENCE': {
            return {
                ...state,
                presence: action.presence || state.presence
            }
        }
        default: {
            return state
        }
    }
}