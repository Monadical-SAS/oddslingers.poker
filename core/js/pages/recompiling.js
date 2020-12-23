// this file is displayed briefly while a JS page is being recompiled by webpack
// it automatically refreshes the page, so that once the webpack process is complete, it shows the new compiled version

window.react_mount.innerHTML = '<center><br/><br/><img src="/static/images/compiling.webp" style="opacity: 0.3;max-width:100%"/><br/><br/><div class="alert alert-warning" style="max-width:300px">Recompiling JS... <i class="fa fa-spinner fa-spin"></i><br/>Page will refresh automatically.</div></center>'

setTimeout(function() {
    window.location = window.location.toString();
}, 1000)
