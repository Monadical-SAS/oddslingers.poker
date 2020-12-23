import {isBaseType} from './javascript.js'


export const stackTrace = (e) =>
    (new Error(e)).stack


export const getShortUUID = (uuid) =>
    uuid.split('-', 1)[0]


export const prettyJSON = (val) => {
    if (val === Infinity)
        return '∞ Infinity'
    else if (typeof(val) === 'number')
        return val.toFixed(2)
    else if (isBaseType(val))
        return JSON.stringify(val)
    else
        return '{' + Object.keys(val).map(key =>
            `${key}: ${prettyJSON(val[key])}`).join('\n') + '}'
}
