import {onSubmitAction} from '@/tournament_summary/reducers'

export const mapStateToProps = (state) => {
    const {
        id, name, tourney_path, table_path, tournament_status, game_variant,
        max_entrants, entrants, buyin_amt, user_funds, results,
        redirect_to_table, presence, tournament_admin, notifications,
        is_private, is_locked
    } = state.tournament_summary

    const is_entrant = global.user && entrants.some(entrant =>
        entrant.username === global.user.username)
    const available_entrances = max_entrants > entrants.length
    const user_has_enough_funds = user_funds
                                  && Number(user_funds) >= Number(buyin_amt)
    const tournament_locked = is_locked

    return {
        id, name, tourney_path, table_path, tournament_status, game_variant,
        max_entrants, entrants, buyin_amt, is_entrant, available_entrances,
        user_has_enough_funds, redirect_to_table, results, presence,
        tournament_admin, notifications, is_private, tournament_locked
    }
}

export const mapDispatchToProps = {
    onSubmitAction
}