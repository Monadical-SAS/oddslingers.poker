/* global $ */
import React from 'react'

import {MAX_CHAT_MSG_LINK_LENGTH} from '@/constants'

export function clone_elem(elem) {
    const old_elem = $(elem)
    if (!old_elem)
        return null
    const old_pos = old_elem.offset()
    if (!old_pos)
        return null
    const new_elem = old_elem.clone()
    new_elem.css('position', 'absolute').css('top', old_pos.top).css('left', old_pos.left)
    new_elem.appendTo($('body'))
    return new_elem
}


export const tooltip = (text, placement='bottom') => ({
    'data-original-title': text,
    onMouseEnter: (e) => {
        $('[data-toggle="tooltip"]').tooltip('hide')
        $(e.target).tooltip()
    },
    onMouseLeave: (e) => {
        $('[data-toggle="tooltip"]').tooltip('hide')
        $(e.target).tooltip('hide')
    },
    'data-toggle': 'tooltip',
    'data-placement': placement,
})

const shortenURL = (url) => {
    if(url.length > MAX_CHAT_MSG_LINK_LENGTH)
        url = url.substring(0,MAX_CHAT_MSG_LINK_LENGTH) + "..."
    return url.replace(/^https?:\/\/(.*)/g, "$1")
}

export const linkifyLinks = (text) => {
    const URLREGEX = /(www\.[^\s]+|https?:\/\/[^\s]+)/g
    const text_linkified = text.split(URLREGEX).map(str =>
        str.match(URLREGEX) ?
        <a href={str.match("http")?str:'//'+str} target="_blank" title={str}>
            {shortenURL(str)}
        </a> :
        str
    )
    return text_linkified
}

export function preventNonNumbers(e) {
    // prevent non-numbers from being typed in
    if (!((e.keyCode > 47 && e.keyCode < 58) || e.keyCode == 8 || e.keyCode == 46 || e.keyCode == 39 || e.keyCode == 37)) {
        e.preventDefault()
    }
}
