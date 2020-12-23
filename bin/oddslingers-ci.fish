#!/usr/bin/env fish

### CONFIG VARS ###
set HOSTNAME "oddslingers-ci"
set ROOT (cd (dirname (status -f)); cd ..; and pwd)
set PY_ROOT "$ROOT/core"
set JS_ROOT "$ROOT/core/js"
set -x ODDSLINGERS_ENV "CI"
set -x PATH ./node_modules/.bin $PATH

set -x SCREENSHOTS_OUT /tmp/screenshots

### Dev Functions ###

function setupjs --description 'Set up the JS environment and packages'
    node --version
    yarn --version
    cd "$JS_ROOT"
    yarn install
    check_node_dependency eslint
    check_node_dependency babel-node
    check_node_dependency webpack
end

function setuppy --description 'Set up the Python environment and packages'
    python3 --version
    pip3 --version
    cd "$PY_ROOT"
    pip3 install --user --no-cache-dir setuptools virtualenv pipenv
    export PIPENV_VENV_IN_PROJECT="enabled"
    pipenv install --dev
end

function lintjs --description 'Run eslint linter on core js javascript'
    cd "$JS_ROOT"
    check_node_dependency eslint
    mkdir -p /tmp/reports/lintjs

    eslint . --format junit --output-file  /tmp/reports/lintjs/results.xml
end

function lintpy --description 'Run flake8 [strict] linter on core python code'
    activate_venv
    cd "$PY_ROOT"
    mkdir -p /tmp/reports/lintpy
    
    check_python_dependency flake8

    # if "strict" is specified as argument, run in strict mode
    flake8 --format junit-xml >  /tmp/reports/lintpy/results.xml
    flake8
end

function testjs --description 'Run core JS tests [--verbose] [--failfast]'
    cd "$JS_ROOT"
    check_node_dependency babel-node

    for file in tests/*.js
        echo $cyan"[*] Test: tests/"$yellow(basename "$file")"$normal"
        babel-node "$file" "$argv"
        # and echo $green"[√]"$normal
        or echo $red"[X]"$normal
        echo ""
    end
end

function testpy --description 'Run core [module] unit tests'
    activate_venv
    mkdir -p /tmp/reports/testpy
    ./manage.py test --parallel 8 $argv
end


function integration_tests --description 'Run core [module] integrations tests against --host [127.0.0.1:8000]'
    activate_venv
    ./manage.py migrate
    ./manage.py runserver --noreload --insecure 127.0.0.1:8000 &
    sleep 8
    curl http://127.0.0.1:8000 > /dev/null
    ./manage.py integration_test $argv
    kill (ps ax | grep -v grep | grep runserver | awk '{print $1}'); or true
end

function screenshots --description 'Run core screenshots'
    activate_venv
    ./manage.py migrate
    ./manage.py create_admins --force
    ./manage.py runserver --noreload --insecure 127.0.0.1:8000 &
    sleep 6
    curl http://127.0.0.1:8000 > /dev/null
    
    # screen resolutions
    
    mkdir "$SCREENSHOTS_OUT"
    set desktop "1440,900"
    set tablet "1024,768"
    set iphone6 "375,667"
    set iphone4 "320,480"

    function screenshot
        google-chrome --headless --disable-gpu --screenshot --window-size="$argv[3]" "http://127.0.0.1:8000$argv[1]"
        mv screenshot.png "$SCREENSHOTS_OUT/$argv[2]"
    end

    # desktop screenshots
    screenshot "/?nowelcome=1" home.png $desktop
    screenshot /tables/ tables.png $desktop
    screenshot /leaderboard/ leaderboard.png $desktop
    screenshot /accounts/login/ login.png $desktop
    screenshot /user/squash/ user.png $desktop
    screenshot /about/ about.png $desktop
    screenshot /support/ support.png $desktop
    screenshot /learn/ learn.png $desktop
    screenshot /speedtest/ speedtest.png $desktop
    
    # tablet screenshots
    screenshot "/?nowelcome=1" home.tablet.png $tablet
    screenshot /tables/ tables.tablet.png $tablet
    screenshot /leaderboard/ leaderboard.tablet.png $tablet

    # iphone 6 screenshots
    screenshot "/?nowelcome=1" home.iphone6.png $iphone6
    screenshot /tables/ tables.iphone6.png $iphone6
    screenshot /leaderboard/ leaderboard.iphone6.png $iphone6

    # iphone 4 screenshots
    screenshot "/?nowelcome=1" home.iphone4.png $iphone4
    screenshot /tables/ tables.iphone4.png $iphone4
    screenshot /leaderboard/ leaderboard.iphone4.png $iphone4

    kill (ps ax | grep -v grep | grep runserver | awk '{print $1}'); or true
end

function compjsall --description 'Compile all JS pages in core in parallel'
    for filename in (command ls "$JS_ROOT"/pages/*.js | cat)
        background compjs (basename $filename) --nohup
    end
end

function compjs --description 'Compile a single JS [page] in core'
    cd "$JS_ROOT"
    check_node_dependency webpack
    webpack
end


### General Helper Functions ###

# Pretty Colors
set arrow "➜ "
set cyan ""
set green ""
set yellow ""
set purple ""
set red ""
set blue ""
set black ""
set white ""
set normal ""

function quiet --description 'Run a command with all stdout and stderr silenced'
    if not count $argv > /dev/null
        return 0
    end

    # quote every argument so spacing is preserved
    set evalstr (string escape -- $argv)
    # eval the command with output silenced
    eval "$evalstr 2>&1 > /dev/null" 2>&1 > /dev/null; and return 0; or return 1
end

function faketty
    unbuffer -p $argv
end

function psax --description 'Filter ps ax output for a specified string'
    ps ax -o pid,command | grep -v grep | grep --color=always -i "$argv"
end

function pid --description 'get the best guess for the pid of a process'
    psax "$argv" | awk '{print $1}'
end

function background --description "Display a process's stdout while it's running in the background"
	bash -c "fish -c 'source ""$ROOT""/bin/oddslingers.fish; ""$argv""' &"
end

function signal --description 'Signal a process thats waiting on a semaphore'
    # if isatty stdin; or test
        quiet command rm ~/tmp/fish_signals/"$argv"
        command touch ~/tmp/fish_signals/"$argv"
    # else
    #     cat - > ~/tmp/fish_signals/"$argv"
    # end
end

function await --description 'Wait for a specified signal from another process'
    set -l signal_name "$argv"
    quiet mkdir -p ~/tmp/fish_signals
    quiet rm ~/tmp/fish_signals/"$signal_name" # clear out old semaphore
    echo %self > ~/tmp/fish_signals/"$signal_name".waiter

    # wait for the semaphore to be set
    while not test -e ~/tmp/fish_signals/"$signal_name"
        sleep 0.05
    end
    rm ~/tmp/fish_signals/"$signal_name".waiter
    sleep 0.05

    if test -s ~/tmp/fish_signals/"$signal_name"
        cat ~/tmp/fish_signals/"$signal_name"
    else
        false
    end
end

function progress_await --description 'Wait for a specified signal and display . every 1 sec'
    set -l signal_name "$argv"
    quiet mkdir -p ~/tmp/fish_signals
    quiet rm ~/tmp/fish_signals/"$signal_name" # clear out old semaphore
    echo %self > ~/tmp/fish_signals/"$signal_name".waiter

    # wait for the semaphore to be set
    while not test -e ~/tmp/fish_signals/"$signal_name"
        echo -n "."
        sleep 1
    end
    # echo
    rm ~/tmp/fish_signals/"$signal_name".waiter
    sleep 0.05

    if test -s ~/tmp/fish_signals/"$signal_name"
        cat ~/tmp/fish_signals/"$signal_name"
    else
        false
    end
end

function find_file --description 'Find [file] in [directory]'
    # collect arguments
    set -l query $argv[1]
    set -l folder "."
    test (count $argv) -gt 1; and set folder "$argv[2]"

    # search current folder for file
    set -l CLICOLOR 0
    set results (/bin/ls "$folder" | grep -i "$query")
    if not test "$results"
        return 1
        # uncomment to change file not found behavior to list dir instead of exiting 1 immediately
        # set results (/bin/ls)
    end

    # if multiple files found, query user for choice (using stderr)
    while [ (count $results) -gt 1 ]
        for line in $results
            echo "$line" | grep --color=auto -i $query 1>&2; or echo "$line" 1>&2
        end
        read -p 'echo $yellow"Pick file: "$normal' query
        set results (for file in $results;
                        echo "$file" | grep -i "$query";
                     end)
    end

    # send result to stdout or exit 1
    not test $results; and return 1
    echo "$results"
end

function _git_branch_name --description 'Get the current git branch name'
    echo (git symbolic-ref HEAD ^/dev/null | sed -e 's|^refs/heads/||')
end

function activate_venv --description 'Activate the core virtual environment'
    cd "$PY_ROOT"

    if [ "$VIRTUAL_ENV" ]
        if not echo "$VIRTUAL_ENV" | grep -q "core/.venv"
            echo $red"[!] Active virtualenv must be located at core/.venv"$normal
            exit 1
        end
        functions -c fish_prompt _old_fish_prompt
        source "$VIRTUAL_ENV"/bin/activate.fish
    else 
        source .venv/bin/activate.fish
    end

    if not test -d .venv
        echo $red"[!] Virtualenv must be present in core/.venv"$normal
        exit 1
    end

    set PYTHON_BIN (which python)

    if not python -c 'import django; print(f"Django v{django.__version__}")' > /dev/null
        echo "[!] Failed to run python, is your virtualenv setup properly in core/.venv?"
        echo "PYTHONPATH: $PYTHONPATH"
        echo "PYTHON BIN: $PYTHON_BIN"
        echo "VIRTUAL_ENV: $VIRTUAL_ENV"
        exit 1
    end
    # echo "[√] Activated .venv: "(which python) (python --version)
end

function check_node_dependency
    cd "$JS_ROOT"
    which $argv | grep -q "^node_modules/.bin/"
    or begin
        echo "Could not find '$argv' command, did you run `yarn` and is ./node_modules/.bin in your \$PATH?"
        exit 1
    end
end

function check_python_dependency
    cd "$PY_ROOT"
    which $argv | grep -q "core/.venv/bin/"
    or begin
        echo "Could not find '$argv' command, did you run `pip install -r requirements.txt` and is your virtualenv in core/.venv activated?"
        exit 1
    end
end


function find_js_page
    set basefilename (basename "$argv[1]")
    set js_src (find_file "$basefilename" $JS_ROOT"/pages/")
    if not test "$js_src"
        echo $red"[X] JS page not found: $basefilename"$normal
        exit 1
    end
    echo $js_src
end
