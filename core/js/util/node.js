import {readFileSync, readdirSync} from 'fs'

// get full paths to all files matching pattern in a folder
export const listFiles = (folder, pattern=/.+\.json/) =>
    readdirSync(folder)
        .filter(filename =>
            filename.match(pattern))
        .map(filename =>
            `${folder}/${filename}`)


// load json from a specified file path
export const loadJson = (path) => {
    const dump_str = readFileSync(path)
    return JSON.parse(dump_str)
}

// import all the files matching a regex pattern in a given folder => {filename: exports}
export const importFiles = (folder, pattern=/.+\.js/i) =>
    readdirSync(folder).reduce((acc, filename) => {
        if (!filename.match(pattern)) {
            return acc
        }
        acc[filename] = require(folder + '/' + filename)
        return acc
    }, {})
