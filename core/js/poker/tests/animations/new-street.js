import {runTests, assertEqual} from '@/util/tests'

import {DUMPS_FOLDER} from '@/constants'
import {loadDebugDump, dispatchActions} from '@/poker/tests/debug_dumps'
import {Table} from '@/pages/table'


export const NEW_STREET_tests = {
    test_translate_to() {
        const page = loadDebugDump(Table, `${DUMPS_FOLDER}/frontend_001.json`)
        const {store, debug_dump} = page
        dispatchActions(store, debug_dump.ws_to_frontend)

        const anim_queue = store.getState().animations.queue

        const new_streets = anim_queue.filter(a =>
            a.source_type.endsWith(':NEW_STREET'))

        if (!new_streets.length) {
            // dump file contains new NEW_STREET actions
            // TODO: add a new frontend_002.json with the necessary NEW_STREET anims for this to work
            return 'Skipped'
        }

        const new_street_translates = new_streets.filter(a =>
            a.type == 'TRANSLATE_TO_TOP')

        console.log(new_streets)

        assertEqual(
            new_street_translates,
            '[{source_type: NEW_STREET, ...}, ...]',
            'No NEW_STREET animations queued after dispatching a hand',
            (a) => a.length > 1,
        )
    },
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
