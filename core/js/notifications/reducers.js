const initial_state = {
	notifications_list: [],
}

export const notifications = (state=initial_state, action) => {
    switch (action.type) {
        case 'UPDATE_GAMESTATE':
            return {
                notifications_list: [
                    ...state.notifications_list,
                    ...(action.notifications || []),
                    ...(action.badge_notifications || []),
                    ...(action.level_notifications || []),
                ]
            }
        case 'NOTIFICATION':
            return {
                notifications_list: [
                    ...state.notifications_list,
                    ...(action.notifications || []),
                    ...(action.badge_notifications || []),
                    ...(action.level_notifications || []),
                ]
            }

        default:
            return state
    }
}
