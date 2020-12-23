import {assertEqual, runTests} from '@/util/tests'

import {Table} from '@/pages/table'


const EXAMPLE_PROPS = {
    "url_name":"Home",
    "url":"http://oddslingers.l/",
    "domain":"oddslingers.l",
    "view":"ui.views.pages.Home",
    "DEBUG":true,
    "GIT_SHA":"6a678584cf8533ceef7e90f32179cb5d37a37669",
    "ENVIRONMENT":"dev",
    "TIME_ZONE":"UTC",
    "user": {
        "id":"57a84da8-a408-46c1-b164-bd7c489687d9",
        "email":"",
        "username":"squash",
        "name":"squashmaster",
        "first_name":"",
        "last_name":"squashmaster",
        "is_active":true,"is_staff":true,"is_authenticated":true,
        "date_joined":"2017-08-09T02:43:13.427Z"
    },
    "gamestate": {
        "table": {
            "id":"243f0a8d-5bc1-4d72-afea-c74f9eec5053",
            "name":"Homepage Table",
            "path":"/table/243f0a8d/",
            "variant":"No Limit Hold 'em",
            "num_seats": 6,
            "btn_idx": 2,
        },
        "players": {},
    },
    "viewers":16,
}


export const table_page_tests = {
    test_post_init_invariants(props=EXAMPLE_PROPS) {
        const page = Table.init(props, false)
        const state = page.store.getState()
        assertEqual(state.animations.queue.length, 1,
            'Failed to create one initial BECOME animation for gamestate')

        assertEqual(state.animations.queue[0].type, 'BECOME',
            'Failed to create one initial BECOME animation for gamestate')

        assertEqual(state.animations.warped_time, 0,
            'Failed to initialize animations with warped_time == 0')

        assertEqual(state.gamestate.version, -1,
            'Failed to load initial gamestate as version -1')

        assertEqual(state.animations.state, {},
            'Animations state was not empty before first animation')
    },
    test_post_first_animation(props=EXAMPLE_PROPS) {
        const page = Table.init(props, false)

        page.store.dispatch({
            type: 'TICK',
            warped_time: 1000,
            former_time: 980,
        })

        const {animations} = page.store.getState()
        assertEqual(animations.warped_time, 1000)
        assertEqual(animations.state.gamestate, props.gamestate)
    },
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
