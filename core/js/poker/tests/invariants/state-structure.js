import {DUMPS_FOLDER} from '@/constants'
import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'
import {
    assert, assertEqual, runTests, testsForFiles, intesecting_values_equals
} from '@/util/tests'
import {loadDebugDump} from '@/poker/tests/debug_dumps'
import {Table} from '@/pages/table'


const structure_invariants = {
    test_init({props, store}) {
        global.DEBUG = false
        let state = store.getState()

        assertEqual(
            state.gamestate.logged_in_player,
            getLoggedInPlayer(props.gamestate.players)
        )

        // make sure nothing is animated initially
        assert(state.animations.state)
        assert(!getGamestate(state))

        // make sure queue only contains initial BECOME animation
        const propstate = {
            table: props.gamestate.table,
            players: props.gamestate.players
        }
        const expected_queue = [{
            type: 'BECOME',
            path: '/gamestate',
            start_state: propstate,
            end_state: null,
            delta_state: null,
            start_time: 0,
            end_time: Infinity,
            duration: Infinity,
            source_type: '-1:SNAPTO',
            split_path: [ 'gamestate' ],
            unit: null,
            merge: false,
            curve: 'linear',
        }]

        assertEqual(
            state.animations.queue[0],
            expected_queue[0],
            'Initial Become looks funny',
            intesecting_values_equals,
        )
        assertEqual(state.animations.queue[0].start_time, 0)
        assertEqual(state.animations.queue[0].end_time, Infinity)
    },
    test_first_tick({props, store}) {
        global.DEBUG = false
        const initial_gamestate = props.gamestate

        // animate first animation
        store.dispatch({
            type: 'TICK',
            warped_time: 2,
            former_time: 1,
            speed: 1,
        })
        // make sure first BECOME animation succeeded
        const {table, players} = getGamestate(store.getState())
        assertEqual(
            {table, players},
            '{table, players}',
            'No gamestate was present after first tick',
            (a) => a.table && a.players)

        assertEqual(table.id, initial_gamestate.table.id)
        assertEqual(players.length, initial_gamestate.players.length)
    },
}


export const state_structure = testsForFiles(
    structure_invariants,
    DUMPS_FOLDER,
    /frontend_.+\.json/,
    (path) => loadDebugDump(Table, path, false))


if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
