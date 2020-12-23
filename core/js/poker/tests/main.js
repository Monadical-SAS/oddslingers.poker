#!/usr/bin/env babel-node
/* Usage:
    ./main.js [--verbose] [--failfast] 
*/

import {importFiles, runTests} from '@/util/tests'

export const poker_tests = {
    components: importFiles(__dirname + '/components'),
    invariants: importFiles(__dirname + '/invariants'),
    animations: importFiles(__dirname + '/animations'),
    pages: importFiles(__dirname + '/pages'),
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
