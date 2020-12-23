// sane javascript modulo
export const mod = (num, amt) =>
    ((num%amt)+amt)%amt

export const sum = (array) =>
    array.reduce((a, v) => (a += v, a), 0)

// equivalent to python range()
export const range = (n) =>
    Array.from(Array(n).keys())

const identity = (item) => item

// return true if item exists before idx in an array
export const exists_before_idx = (array, idx, item, key=identity) =>
    !(array.map(other => key(other)).indexOf(key(item)) == idx)

// return an array with duplicate items removed (using key function for comparison)
export const uniquify = (array, key=identity) =>
    array.filter((item, idx) =>
        !exists_before_idx(array, idx, item, key))

// iterate over an array in reverse (generator)
export function *reversed(iterator) {
    for (let idx=iterator.length-1; idx >= 0; idx--) {
        yield iterator[idx]
    }
}

// rotate an array by count positions
export function rotated(array, count=1) {
    array = [...array]

    const len = array.length >>> 0       // convert to uint
    count = count >> 0              // convert to int

    // convert count to value in range [0, len)
    count = ((count % len) + len) % len

    // use splice.call() instead of array.splice() to make function generic
    Array.prototype.push.apply(array, Array.prototype.splice.call(array, 0, count))
    return array
}

// flatten a nested array that's nested one level deep
export const flattened = (array) =>
    [].concat.apply([], array)


// remove a key:value from the object and return the val
export function pop(dict, key, default_to) {
    const val = dict[key]
    delete dict[key]
    return val === undefined ? default_to : val
}

// left-justify a str by amt, using padding char=' ' (same as ljust in python)
export const ljust = (str, width, padding=" ") => {
    if (str.length < width)
        return str + padding.repeat(width - str.length)
    else
        return str + ''
}

// right-justify a str by amt, using padding char=' ' (same as rjust in python)
export const rjust = (str, width, padding) => {
    padding = padding || " "
    padding = padding.substr(0, 1)
    if (str.length < width)
        return padding.repeat(width - str.length) + str
    else
        return str + ''
}

// center a str by amt, using padding char=' ' (same as center in python)
export const center = (str, width, padding) => {
    padding = padding || " "
    padding = padding.substr(0, 1)
    if (str.length < width) {
        const len = width - str.length
        const remain = (len % 2 == 0) ? "" : padding
        const pads = padding.repeat(parseInt(len / 2))
        return pads + str + pads + remain
    }
    else
        return str + ''
}

export const round = (num, decimal_places=0) =>
    Math.round(num * (10**decimal_places)) / (10**decimal_places)


export const chipAmtStr = (str, rough=false) => {
    const num_chips = Number(str)
    if (num_chips === 0) return num_chips.toLocaleString()
    if (rough) {
        if (num_chips >= 10**9) {
             // 9,643,232,000 -> 9.6B
            return `${round(num_chips/10**9, 1).toLocaleString()}B`
        } else if (num_chips >= 10**6) {
            // 9,643,232 -> 9.6M
            return `${round(num_chips/10**6, 1).toLocaleString()}M`
        } else if (num_chips >= 10**3) {
            // 106,358 -> 106.4K
            return `${round(num_chips/10**3, 1).toLocaleString()}K`
        }
    } else {
        if (num_chips % 10**9 == 0 && num_chips < 10**12)
            return `${(num_chips / 10**9).toLocaleString()}B`
        if (num_chips % 10**8 == 0 && num_chips >= 10**9 && num_chips < 10**12)
            return `${round(num_chips / 10**9, 1).toLocaleString()}B`
        if (num_chips % 10**7 == 0 && num_chips >= 10**9 && num_chips < 10**12)
            return `${round(num_chips / 10**9, 2).toLocaleString()}B`
        if (num_chips % 10**6 == 0 && num_chips < 10**9)
            return `${(num_chips / 10**6).toLocaleString()}M`
        if (num_chips % 10**5 == 0 && num_chips >= 10**6 && num_chips < 10**9)
            return `${round(num_chips / 10**6, 1).toLocaleString()}M`
        if (num_chips % 10**4 == 0 && num_chips >= 10**6 && num_chips < 10**9)
            return `${round(num_chips / 10**6, 2).toLocaleString()}M`
        if (num_chips % 10**3 == 0 && num_chips < 10**6)
            return `${(num_chips / 10**3).toLocaleString()}K`
        if (num_chips % 10**2 == 0 && num_chips >= 10**3 && num_chips < 10**6)
            return `${round(num_chips / 10**3, 1).toLocaleString()}K`
        if (num_chips % 10**1 == 0 && num_chips >= 10**3 && num_chips < 10**6)
            return `${round(num_chips / 10**3, 2).toLocaleString()}K`
    }
    return num_chips.toLocaleString()
}

// java-style hashCode for any strings
export const hashCode = (str) => {
    if (str.length == 0) return 0

    let hash = 0
    for (let character of str) {
        hash = ((hash << 5) - hash) + (
            character.charCodeAt ?
                character.charCodeAt()  // convert string characters to ints
              : character)
        hash = hash & hash              // Convert to 32bit integer
    }
    return hash
}

// equivalent to {val: key for key, val in obj.items()}
export const flipObj = (obj) =>
    Object.keys(obj).reduce((acc, key) => {
        const val = obj[key]
        acc[val] = key
        return acc
    }, {})

// equivalent to {key: func(key, val) for key, val in obj.items()}
export const mapObj = (obj, func) =>
    Object.keys(obj).reduce((acc, key) => {
        acc[key] = func(key, obj[key])
        return acc
    }, {})


// equivalent to {key: val for key, val in obj.items() if func(key, val)}
export const filterObj = (obj, func) =>
    Object.keys(obj).reduce((acc, key) => {
        if (func(key, obj[key])) {
            acc[key] = obj[key]
        }
        return acc
    }, {})

// Create an object counting the repeated elements of an array
export const groupByRepeated = (elems) => {
    const countedElems = {}
    for (let e of elems) {
        countedElems[e] = 1 + (countedElems[e] || 0)
    }
    return countedElems
}

// count the number of values in on object that satisfy a given condition
export const countLeaves = (obj, condition=isBaseType) => {
    if (condition(obj)) {
        return 1
    } else if (typeof(obj) === 'object') {
        return sum(Object.values(obj).map(val => countLeaves(val, condition)))
    } else {
        return 0
    }
}

// memoize any **pure** function, works great with immutablejs args as
export function memoize(fn) {
    // it only has to store the hashcode int and not the full json of the arguments
    return function () {
        let args = Array.prototype.slice.call(arguments)
        let hash = ""
        let i = args.length
        let currentArg = null
        fn.memoize || (fn.memoize = {})
        while (i--) {
            currentArg = args[i]
            // arg hash is immutablejs hashCode if present, otherwise Str or JSON of object
            const arg_hash = currentArg.hashCode ?
                currentArg.hashCode()
              : (JSON.stringify(currentArg) || currentArg.toString())
            hash += arg_hash
        }
        return (hash in fn.memoize) ?
            fn.memoize[hash]
          : fn.memoize[hash] = fn.apply(this, args)
    }
}

export const generateUUID = () => {
    // uuid is always unique because it's a hash of a precision timestamp + random seed
    var d = new Date().getTime();
    if (typeof global.performance !== 'undefined' && typeof global.performance.now === 'function'){
        d += global.performance.now();  //use high-precision timer if available
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = (d + Math.random() * 16) % 16 | 0;
        d = Math.floor(d / 16);
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}
 

export const setIntersection = (set1, set2) => [...set1].filter(x => set2.has(x))
export const setDifference = (set1, set2) => [...set1].filter(x => !set2.has(x))

const base_types = ['string', 'number', 'boolean', 'symbol', 'function']
export function isBaseType(item) {
    // false if item is a dict, true for everything else
    if (item === null || item === undefined) {
        return true
    } else if (base_types.includes(typeof item)) {
        return true
    } else if (Array.isArray(item)) {
        return true
    }
    return false
}
global.isBaseType = isBaseType

export function deepMerge(obj1, obj2) {
    if (isBaseType(obj1) || isBaseType(obj2)) {
        return obj2
    } else {
        const obj1_keys = new Set(Object.keys(obj1))
        const obj2_keys = new Set(Object.keys(obj2))
        const both_keys = setIntersection(obj1_keys, obj2_keys)
        const only_obj1 = setDifference(obj1_keys, obj2_keys)
        const only_obj2 = setDifference(obj2_keys, obj1_keys)

        const new_obj = {}

        // merge any data thats in both dicts
        both_keys.reduce((new_obj, key) => {
            new_obj[key] = deepMerge(obj1[key], obj2[key])
            return new_obj
        }, new_obj)

        // add values only in obj1
        only_obj1.reduce((new_obj, key) => {
            new_obj[key] = obj1[key]
            return new_obj
        }, new_obj)

        // add values only in obj2
        only_obj2.reduce((new_obj, key) => {
            new_obj[key] = obj2[key]
            return new_obj
        }, new_obj)

        return new_obj
    }
}
global.deepMerge = deepMerge

export function select(obj, selector) {
    // ({a: {b: 2}}, '/a/b') => 2                   Get obj at specified addr (works with array indicies)
    if (selector === '/') return obj
    if (selector[0] !== '/') throw `Invalid selector! ${selector}`
    for (let key of selector.split('/').slice(1)) {
        obj = obj[key]
    }
    return obj
}
global.select = select

export function patch(obj, selector, new_val, merge=false, mkpath=false) {
    // ({a: {b: 2}}, '/a/b', 4) => {a: {b: 4}}      Set obj at specified addr (works with array indicies)
    if (selector === '/') return new_val
    if (!selector || selector[0] !== '/') throw `Invalid selector! ${selector}`
    const keys = selector.split('/').slice(1)
    const last_key = keys.pop()
    if (last_key == '') {
        console.log({obj, selector, new_val, merge, mkpath})
        throw 'Patch paths must not have trailing slashes!'
    }
    let parent = obj
    for (let key of keys) {
        // create path if any point is missing
        if (mkpath && (parent[key] === undefined || parent[key] === null)) {
            parent[key] = {}
        }
        parent = parent[key]
    }
    if (merge) {
        parent[last_key] = deepMerge(parent[last_key], new_val)
    } else {
        parent[last_key] = new_val
    }
    return obj
}

export const truncText = (str, len=30) => {
    return str.length <= len ? str : str.substring(0, len) + "..."
}

export const formatStr = (str, ...args) => {
    let i = 0
    return str.replace(/{}/g, () => typeof args[i] != 'undefined' ? args[i++] : '')
}
