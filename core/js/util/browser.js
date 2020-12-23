import {Howl} from 'howler'

// parse URL parameters into a javascript dictionary
export function getUrlParams(search) {
    search = search || global.location.search
    let hashes = search.slice(search.indexOf('?') + 1).split('&')
    let params = {}
    hashes.map(hash => {
        let [key, val] = hash.split('=')
        params[key] = decodeURIComponent(val)
    })

    return params
}

export const getSearchHashInUrl = () => {
    const url_params = getUrlParams(window.location.href)
    const search_param = url_params.search
    return search_param ? search_param : ''
}

// trigger a function 1nce when it's being called repeatedly, after given timeout
export function debounce(func, wait, immediate) {
    let timeout
    return function() {
        const context = this
        const args = arguments
        let later = function() {
            timeout = null
            if (!immediate)
                func.apply(context, args)
        }
        const callNow = immediate && !timeout
        clearTimeout(timeout)
        timeout = setTimeout(later, wait)
        if (callNow)
            func.apply(context, args)
    }
}

// fetch list of image urls in advance, so they don't have to load when displayed
export function preloadImages(images) {
    (images || []).map(src => {
        let img = new Image()
        img.src = src
        // console.log(`Preloaded image ${src}`)
    })
}

export const localStorageSet = (key, value) => {
    if (value.toJS)
        value = value.toJS()
    if (global.localStorage) {
        global.localStorage.setItem(key, JSON.stringify(value))
        return true
    }
    return false
}

export const localStorageGet = (key, default_value=null) => {
    if (global.localStorage) {
        return JSON.parse(global.localStorage.getItem(key)) || default_value
    }
    return default_value
}

export const requestDesktopNotify = () => {
    console.log('Asking for desktop notification permission...')
    Notification.requestPermission(function (permission) {
        console.log('Desktop notification permission ' + permission)
    })
}

export const desktopNotify = (title, body, icon) => {
    const options = {
        body: body || '',
        icon: icon || '/static/images/chips.png',
    }

    // Let's check if the browser supports notifications
    if (!("Notification" in global)) {
        console.log(`Notification [${title}]: ${body}`)
    }

    // Let's check whether notification permissions have already been granted
    else if (Notification.permission === "granted") {
        new Notification(title, options)
        return true
    }

    // Otherwise, we still need to ask the user for permission using askForDesktopNotifications
    else if (Notification.permission !== 'denied') {
        return false
    }
    return false
}

export function select_text(elemt_id) {
    const text_elem = document.getElementById(elemt_id)

    if (text_elem !== null) {
        const range = document.createRange()
        range.selectNodeContents(text_elem)
        const selection = window.getSelection()
        selection.removeAllRanges()
        selection.addRange(range)
    }
}

export const is_centered = () =>
    global.innerWidth <= 1200

export const is_mobile = () =>
    global.innerWidth < 767

export const is_portrait = () =>
    global.innerWidth < global.innerHeight

export const getWindowWidth = () =>
    global.innerWidth

export const getWindowHeight = () =>
    global.innerHeight - (is_mobile() ? 40 : 52)

export function getPageSize(elemt_id) {
    const maxHeight = $(elemt_id).height()
    const maxWidth = $(elemt_id).width()
    return {maxWidth, maxHeight}
}

function scalePages(page, move=true, c_width=true, c_height=true) {
    const basePage = {
        width: 1510,
        height: is_mobile() ? 1050 : 1000,
        scale: 1,
        scaleX: 1,
        scaleY: 1,
    }
    const {maxWidth, maxHeight} = getPageSize('#react-table-page')
    const newBasePage = {...basePage}
    const scaleX = maxWidth / newBasePage.width
    const scaleY = (maxHeight + 50) / newBasePage.height
    newBasePage.scaleX = scaleX
    newBasePage.scaleY = scaleY
    newBasePage.scale = Math.min(scaleX, scaleY)
    const scaled_width = (is_centered() && !is_mobile()) ? 1120 : newBasePage.width
    const newLeftPos = Math.abs(Math.floor(((scaled_width * newBasePage.scale) - maxWidth)/2))
    const new_width = c_width ? newBasePage.scale : 1
    const new_height = c_height ? newBasePage.scale : 1
    page.attr(
        'style',
        (move ? `left: ${newLeftPos}px;`: '') +
        `-webkit-transform: scale(${new_width}, ${new_height});` +
        `-ms-transform: scale(${new_width}, ${new_height});` +
        `-moz-transform: scale(${new_width}, ${new_height});` +
        `transform: scale(${new_width}, ${new_height});`
    )
}

export function setResizeTable() {
    const $page = $('.table')
    scalePages($page)

    $(window).resize(function () {
        scalePages($page)
    })
}

export const play_sound = (sound_path) => {
    const audio = new Howl({
        src: sound_path
    })
    audio.play()
}

export const change_favicon = (icon_path) => {
    let link = document.createElement('link')
    link.href = icon_path
    link.rel = 'icon'
    let old_link = document.querySelectorAll("link[rel*='icon']")
    if (old_link) {
        for (let elem of old_link) {
            document.head.removeChild(elem)
        }
    }
    document.head.appendChild(link)
}

export const pageIsHidden = () =>
    document.hidden || document.msHidden || document.webkitHidden


export const onKeyPress = (keyname, handler, modifier=null) => {
    // https://stackoverflow.com/questions/37557990/detecting-combination-keypresses-control-alt-shift
    global.addEventListener("keydown", (e) => {
        if (!modifier || e[modifier]) {
            if (e.keyCode == keyname || String.fromCharCode(e.keyCode).toLowerCase() == keyname) {
                handler(e)
            }
        }
    }, true)
}

export const onKonamiCode = (handler) => {
    let kkeys = []
    const konami = "38,38,40,40,37,39,37,39,66,65"
    global.addEventListener("keydown", (e) => {
        kkeys.push(e.keyCode)
        if (kkeys.toString().indexOf(konami) >= 0) {
            console.log('Konami code activated!')
            global.konami_on = true
            kkeys = []
            handler(e)
        }
        return true
    }, true)
}

export const getUserBalance = (callback) => {
    $.get('/api/user/balance/', {}, function (resp) {
        if (resp.balance !== undefined) {
            global.user.balance = Number(resp.balance)
            if (callback)
                callback(Number(resp.balance))
        }
    })
}

export const asyncGetUserBalance = (callback) => {
    if (global.addEventListener && global.user && global.user.username) {
        global.addEventListener('load', getUserBalance.bind(this, callback), true)
    }
}

export const openNewTab = (link) => {
    global.open(link)
}

export const isEmbedded = (context=global.self) => 
    global.top !== context


export const getCookie = (name) => {
    let cookieValue = null
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';')
        for (let i = 0; i < cookies.length; i++) {
            const cookie = $.trim(cookies[i])
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = global.decodeURIComponent(cookie.substring(name.length + 1))
                break
            }
        }
    }
    return cookieValue
}
