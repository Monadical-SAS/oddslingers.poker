/**
 * Animation system stubs — Phase 3
 * redux-time has been removed. These stubs preserve the interface for future re-enablement.
 * To restore animations: replace this module with actual redux-time (or equivalent) imports.
 */

export const animationsReducer = (state = {queue: [], current_time: 0, paused: false, speed: 1}, action) => state

export const startAnimation = (store, initial_state = {}, autostart = false) => ({
    getActualTime: () => Date.now(),
    setActualTime: () => {},
    stop: () => {},
})

export const initial_state = {
    queue: [],
    current_time: 0,
    paused: false,
    speed: 1,
}
