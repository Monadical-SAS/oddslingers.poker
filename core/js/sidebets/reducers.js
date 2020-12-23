const initial_state = {
	bets: [],
    total: 0
}

export const sidebet = (state=initial_state, action) => {
    switch (action.type) {
        case 'UPDATE_SIDEBET': {
            return {
                ...state,
                bets: action.bets,
                tables: action.tables,
                total: action.total
            }
        }
        case 'UPDATE_GAMESTATE': {
            return {...state, bets: action.sidebets}
        }
        default: {
            return state
        }
    }
}
