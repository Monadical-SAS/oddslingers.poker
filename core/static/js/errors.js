window.PYTHON_FAILURE_MSG = 'We failed to render the page due to an error.'
window.JS_LOAD_FAILURE_MSG = 'The UI failed to load due to an error.' + (window.DEBUG ? ' Try rebuilding JS files with `<b>../oddslingers compjs</b>`.' : '')
window.ERROR_HELP_MSG = 'Check the console for error details. If you urgently need to access data, try the <a href="/admin/">Django Admin</a>.'
window.COMPONENT_404_MSG = 'UI component was not found.'
window.EMAIL_HELP_TXT = "Sorry you encountered a problem on Oddslingers!%0AWe'll try to get back to you as soon as possible, we just need some information to help resolve the issue.%0A%0APlease describe your issue here:%0A    What happened? Did you see any errors?%0A%0ASteps you took before you encountered the issue:%0A    1. %0A    2. %0A    3. %0A    ...";

// display alert on page if scripts fail to load
window.onerror = function(error, url, line, python_exc) {
    window.LAST_ERROR = {
        error: error,
        url: url,
        line: line,
        python_exc: python_exc,
    }

    if (window.store) {
        // if (error.startsWith('Warning: validateDOMNesting'))
        //     return    // ignore DOM nesting errors
        // if (error.startsWith('Uncaught Invariant Violation'))
        //     return    // TODO: don't ignore these

        try {
            window.store.dispatch({type: 'NOTIFICATION', notification: {
                text: error,
                style: error.toLowerCase().startsWith('warning') ? 'warning' : 'danger',
            }})
        }
        catch(err) {console.log(err)}
    }
    var show_advanced = window.DEBUG || (window.user && window.user.is_staff);
    $('#react-loading-icon').css('animation', 'none')
    $('#react-loading-icon').css('opacity', 1)
    $('#react-loading svg').remove()
    $('#react-loading .failed').removeClass('alert-warning').addClass('alert-danger')
    $('#react-loading .failed').html(!Number(python_exc) ?
        (window.PYTHON_FAILURE_MSG + (show_advanced ? ('<br/><br/><b>' + (python_exc || 'JS Exception') + '</b>') : ''))
      : window.JS_LOAD_FAILURE_MSG);
    if (show_advanced) {
        $('#react-loading .failed').append('<br><br><b>' + url + ':'+ (line || 'stderr') + '</b><br><br><pre>' + JSON.stringify(error).replace(/ \/.+?core\//gim, " ") + '</pre><small>' + ERROR_HELP_MSG + '</small>');
    }
    var subject = "Page Loading Error for " + (window.user ? window.user.username : 'Anonymous User');
    var help_text = window.EMAIL_HELP_TXT
    var support_info = "================================%0AOn URL: " + window.location + "%0A" + encodeURIComponent(python_exc) + "%0A" + encodeURIComponent(url) + ":" + encodeURIComponent(line) + "%0A" + encodeURIComponent(error);
    var support_link = "mailto:support@oddslingers.com?subject=" + subject + "&body=" + help_text + "%0A%0A" + support_info;
    $('#react-loading .failed').append('<br><br><a href="' + support_link + '">Contact support</a> to report the error and get help.');
    $('#react-loading').append('<img height="80px" src="/static/images/sad-mac-face.png">');
    $('#react-loading .failed').show();

    // Ask user for crash report
    // if (!window.DEBUG && window.reportSentryError) {
    //     setTimeout(function() {
    //         reportSentryError(error);
    //     }, 2000);
    // }
};
window.console._error = window.console.error
window.console.error = function(error) {
    // browserfiy syntaxerrors are shown by calling console.error
    // we catch that here to display them on the page as well as in console
    window.console._error.apply(window.console, arguments)
    window.onerror(error)
}
window.on404 = window.onerror.bind(this,
    window.COMPONENT_404_MSG,
    window.component_url,
    404
)
// show any errors passed from the backend via render_error()
if (window.props.error) {
    window.onerror(window.props.details, window.props.url, window.props.line, window.props.error)
}
