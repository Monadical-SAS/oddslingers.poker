/* This code parses CSS properties out of browser styleSheet objects */

export const getCenter = ({width, height}) => 
    ({top: height/2, left: width/2})

export const getStylesheet = () =>
    document.styleSheets

export const toVW = (px) =>
    (px/global.innerWidth) * 100

export const getCSS = (stylesheet, selector, property) => {
    // search backwards because the last match has higher precedence
    for (let s=stylesheet.length-1; s>=0; s--) {
        const cssRules = stylesheet[s].cssRules || stylesheet[s].rules || []  // IE support
        for (let rule of cssRules) {
            if (rule.selectorText === selector)
                return rule.style[property]
        }
    }
    return null
}

export const parseToVW = (selector, property) => {
    const stringVal = getCSS(getStylesheet(), selector, property)

    if (!stringVal) {
        console.log('%cINVALID SELECTOR', 'color:red', {selector, property, stringVal})
        throw `Couldn't find CSS value (is there a rule defined for the given selector?)`
    }

    if (stringVal.endsWith('px')) {
        console.log(
            '%cWARNING, USING CSS PX VALUE', 'color:orange',
            {selector, property, stringVal},
            '(vw should be used for all table values instead of px or %)',
        )
        return Number(toVW(stringVal.slice(0, -2)))
    }
    if (stringVal.endsWith('vw')) {
        return Number(stringVal.slice(0, -2))
    }
    if (stringVal.endsWith('%')) {
        console.log('%cINVALID VALUE', 'color:red', {selector, property, stringVal})
        throw 'Parsing CSS percentage values is not supported, please change the value to px or vw'
    }

    const num = Number(stringVal)
    if (Number.isNaN(num))
        throw `Unable to parse CSS value ${stringVal} -> ${num}`

    return num
}

export const getDimensions = (selector) => ({
    width: parseToVW(selector, 'width'),
    height: parseToVW(selector, 'height'),
})
