import React from 'react'
import {connect as reduxConnect} from 'react-redux'
import {getCookie} from '@/util/browser'

// turn {mapStateToProps, mapDispatchToProps, render}
// into a connected redux component
export const connect = (container) => {
    const bound = reduxConnect(
        container.mapStateToProps,
        container.mapDispatchToProps,
    )(container.render)

    // occasionally needed for testing
    // bound.mapStateToProps = container.mapStateToProps
    // bound.mapDispatchToProps = container.mapDispatchToProps
    return bound
}

global.csrftoken = getCookie('csrftoken')

export const CSRFToken = () =>
    <input type="hidden" name="csrfmiddlewaretoken" value={global.csrftoken}/>
