// Browser protoype extensions
// This function is a bad idea, but that's what happens when a bunch of
// python devs get fed up with javascript stupidity.  Try not to put anything
// here unless you absolutely need it

// ** don't put anything too short to be grep-pable here, **
// ** in case it needs to be refactored out later **

// ** these are only for things needed in HTML files!!! if you're using these
// ** functions in React code you'll be fired (jk).  Instead, add stuff you need
// ** in JS code to util/javascript.js so that it's clean and testable

function g() {
    return window.page.store.getState().animations.state.gamestate
}

function s() {
    return window.page.store.getState()
}
function d(action) {
    return window.page.store.dispatch(action)
}
window.g = g
window.s = s
window.d = d


function applyOverrides() {
    // allow mapping over node lists
    if (window.Symbol && window.HTMLCollection && window.NodeList) {
        HTMLCollection.prototype[Symbol.iterator] = Array.prototype[Symbol.iterator]
        NodeList.prototype.map = Array.prototype.map
        NodeList.prototype.filter = Array.prototype.filter
        NodeList.prototype.reduce = Array.prototype.reduce
    } else {
        console.log('[!] WARNING: Running in an old/unsupported browser!')
    }
}
applyOverrides();
window.applyOverrides = applyOverrides;

var is_staff = window.user && (window.user.is_staff || window.user.is_superuser)


if (!window.DEBUG && !is_staff) {
    console.log('If you find a bug, let us know ;)  %cbugs@oddslingers.com',    'color: green;font-family: serif')
    console.log('Help us build Oddslingers:         %ccareers@oddslingers.com', 'color: green;font-family: serif')
}


window.addEventListener('load', function() {
    // Django CSRF
    function getCookie(name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = $.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    window.csrftoken = getCookie('csrftoken');
    function csrfSafeMethod(method) {
        // these HTTP methods do not require CSRF protection
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", window.csrftoken);
            }
        }
    });
})
