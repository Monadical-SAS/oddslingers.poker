import 'colors'
import isEqual from 'lodash/isEqual'
import {inspect} from 'util'

import {GRATER_ROOT, JS_ROOT} from '@/constants'
import {ljust, countLeaves} from '@/util/javascript'
import {loadJson, listFiles, importFiles} from '@/util/node'
export {importFiles}


// main test runner, takes an object containing many functions,
// the path used to show which file is being tested, and command line args
export const runTests = (module, filename='', argv=[]) => {
    // parse command line args
    global.FAILFAST = argv.includes('--failfast')
    global.VERBOSE = (argv.includes('-v')
                      || argv.includes('--verbose'))

    // print starting debug info
    if (global.VERBOSE) {
        const short_filename = filename.split(`/${JS_ROOT}/`).slice(-1)[0]
        const test_count = countLeaves(module, a => typeof(a) === 'function')
        console.log(`[+] Running ${test_count} tests: js/${short_filename}`.cyan)
        // console.log(inspect(module, {colors: 1, depth: 6}))
        console.log('-------------------------------------------------------')
    }
    // run the test suite (timed)
    const start_time = Date.now()
    const results = runModuleFunctions(module, filename, global.FAILFAST)
    const duration = ((Date.now() - start_time)/1000).toLocaleString()

    // print finishing debug info
    const num_ran = countLeaves(results)
    const num_failed = countLeaves(results, a => a.stack)
    if (global.VERBOSE) {
        console.log('\n-------------------------------------------------------')
        if (num_failed) {
            console.log(`[X] Ran ${num_ran} tests in ${duration}s, ${num_failed} tests failed. ${global.FAILFAST ? '(FAILFAST)' : ''}`.red)
        } else {
            console.log(`[√] Ran ${num_ran} tests in ${duration}s, all tests passed.`.green)
        }
        console.log(inspect(results, {colors: 1, depth: 6}))
    } else {
        const num_failed = countLeaves(results, a => a.stack)
        if (num_failed) {
            console.log(`\n[X] Ran ${num_ran} tests in ${duration}s, ${num_failed} tests failed. ${global.FAILFAST ? '(FAILFAST)' : ''}`.red)
            console.log(inspect(results, {colors: 1, depth: 6}))
        }
    }
    process.exit(num_failed ? 1 : 0)
}


// run all the functions stored in an object, at any level in the object
export const runModuleFunctions = (object, path='', failfast=false) => {
    // base case: value is a function, we run it and return result
    if (typeof(object) === 'function') {
        global.path = path  // used by stacktrace to show a prettier call path
        return object()
    }
    // recursive case: value is an object, recurse on each child value
    else if (typeof(object) === 'object') {
        const return_values = {}
        for (let key of Object.keys(object)) {
            // for each value, run it and store the result in return_values
            try {
                const result = runModuleFunctions(object[key], `${path}/${key}`, failfast)
                return_values[key] = result === undefined ? 'Passed' : result
            } catch(e) {
                return_values[key] = e
                if (failfast) break
            }
        }
        return return_values
    }
}

// Takes an Error.stack and produces a shortened, cleaner stacktrace with coloring
const prettifyCallStack = (stack) => {
    const shortened_paths = stack.replace(/\(\/.+\/core\/(.+)\)$/gm, "($1)")
    const test_only_paths = (shortened_paths
                                .split('\n')
                                .filter(line =>
                                    line.includes('js/')
                                    && line.includes(' (')
                                    && !line.startsWith('    at runModuleFunctions')))

    const justified_paths = test_only_paths.map(line => {
        // left-justify the function names
        const [pt1, pt2] = line.split(' (', 2)
        const justified_line = `${ljust(pt1, 30)} (${pt2}`
        // highlight filenames in paths
        const ending = justified_line.split('/').slice(-1)[0]
        const pretty_line = justified_line.replace(ending, ending.yellow)
        return pretty_line
    })
    return justified_paths.join('\n') + '\n'
}

// given Error.stack and/or a path, figure out the best display name for a test
const testName = (stack, path) => {
    if (path) {
        const func_name = path.split('.js/').slice(-2)[1]
        const filename = path.split(func_name)[0].split('/').slice(-2)[0]
        return `${filename.yellow.underline} ${func_name.replace('/', '.')}`
    }
    const test_line = stack.split('\n').filter(line =>
        line.startsWith('    at test_') || line.startsWith('    at Object.test_'))[0]
    const test_name = test_line.split(' at ')[1].split(' ')[0]
    return test_name.replace('Object.', '')
}

export function log() {
    const args = Array.prototype.slice.call(arguments)
    args.map(a => {
        if (typeof(a) === 'string')
            process.stdout.write(a, + " ")
        else
            process.stdout.write(inspect(a, {colors: 1}) + " ")
    })
    process.stdout.write('\n')
}

const is_truthy = (a) => !!a
export const json_equals = (a, b) => JSON.stringify(a) === JSON.stringify(b)
export const intesecting_values_equals = (got, expected) => {
    return Object.keys(expected).every((key) => {
        return isEqual(got[key], expected[key])
    })
}

export const assert = (val, error_msg='', condition=is_truthy) => {
    return assertEqual(val, 'Truthy', error_msg, condition)
}

export const assertEqual = (val1, val2, error_msg='', condition=isEqual) => {
    if (!condition(val1, val2)) {
        const assertion_error = (new Error('AssertionError'))
        const test_name = testName(assertion_error.stack, global.path)
        const test_path = global.path.split(`/${GRATER_ROOT}/`).slice(-1)[0]
        const pretty_path = test_path.replace('js/', '/').split('.js').join('.js\n    ')
        console.log('\n[X] AssertionError:'.red, test_name)
        if (error_msg.length)
            console.log(`\n${error_msg}`)
        console.log()
        log('Expected\n'.green, val2)
        log('\nGot\n'.red, val1)
        console.log()
        console.log(prettifyCallStack(assertion_error.stack))
        console.log(`    ${pretty_path}\n`)
        throw assertion_error
    }
    if (process) process.stdout.write('.')
    else console.log('.')
    return true
}


// take a tests module, and run every test against every file in the given folder
export const testsForFiles = (tests, folder, pattern, setUp=loadJson) => {
    const module = {}
    for (let test of Object.keys(tests)) {
        module[test] = {}
        for (let filename of listFiles(folder, pattern)) {
            const test_func = tests[test]
            const func_args = setUp(filename)
            const short_filename = filename.split('/').slice(-1)[0]
            module[test][short_filename] = test_func.bind(module[test], func_args)
        }
    }
    return module
}
