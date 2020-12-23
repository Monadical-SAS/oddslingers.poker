#!/usr/bin/env fish

### CONFIG VARS ###
set HOSTNAME (hostname)
set ROOT (cd (dirname (status -f)); cd ..; and pwd)
set REPO_DIR (cd (dirname (status -f)); cd ..; and pwd)
set DATA_DIR "$REPO_DIR/data"
set PY_ROOT "$ROOT/core"
set JS_ROOT "$ROOT/core/js"
set DJANGO_USER (who | awk '{print $1}')

if [ "$DJANGO_USER" = "" ]
    set DJANGO_USER (whoami)
end

set POSTGRES_DB "oddslingers"
switch "$HOSTNAME"
    case 'oddslingers-prod'
        echo "oddslingers cmd should only be run on DEV machines (not PROD or BETA)."
        exit 1
    case 'oddslingers-prod-bulk'
        echo "oddslingers should only be run on DEV machines (not PROD or BETA)."
        exit 1
    case 'oddslingers-beta'
        echo "oddslingers should only be run on DEV machines (not PROD or BETA)."
        exit 1
    case 'oddslingers-beta-bulk'
        echo "oddslingers cmd should only be run on DEV machines (not PROD or BETA)."
        exit 1
    case '*'
        set -x ODDSLINGERS_ENV "DEV"
end


### Dev Functions ###

function start --description 'Run the django development server'
    activate_venv
    cd "$PY_ROOT"
    sudo supervisorctl reload
    sudo supervisorctl update
    sleep 4
    sudo supervisorctl status all
    ./manage.py rundramatiq --threads 1 --processes 1 | sed -n -e '/Worker process is ready for action/,$p' &
    ./manage.py runserver
end

function stop --description 'Stop the django development server'
    sudo supervisorctl stop oddslingers-django:
    sudo supervisorctl stop oddslingers-bg:
    sudo pkill runserver
    sudo pkill rundramatiq
end

function manage --description 'Run manage.py [cmd] [args] e.g. migrate'
    activate_venv
    cd "$PY_ROOT"
    env DJANGO_DEBUG_HELPERS=1 ./manage.py $argv
end

function shell --description 'Open a django shell_plus'
    activate_venv
    cd "$PY_ROOT"
    env DJANGO_DEBUG_HELPERS=1 PYTHONSTARTUP=$PY_ROOT/oddslingers/save_ipython_history.py ./manage.py shell_plus
end

function tests --description 'Run all linters and tests'
    activate_venv
    echo -e "JS Linter:\n===================================="
    lintjs

    echo -e "\nJS Tests:\n===================================="
    testjs

    echo -e "\n\nPython Linter:\n===================================="
    lintpy

    echo -e "\nPython Tests:\n===================================="
    testpy

    echo -e "\nHandHistory Dumps:\n===================================="
    ls dumps/*.json

    echo -e "\nIntegration Tests:\n===================================="
    if psax runserver | grep -q './manage.py'
        integration_tests
    else
        echo "Skipping integration tests because runserver is not running."
    end
end

function lintjs --description 'Run eslint linter on core js javascript'
    cd "$JS_ROOT"
    check_node_dependency eslint
    eslint .
end

function lintpy --description 'Run flake8 [strict] linter on core python code'
    activate_venv
    check_python_dependency pygmentize
    check_python_dependency flake8
    cd "$PY_ROOT"

    # if "strict" is specified as argument, run in strict mode
    if [ "$argv" ]
        flake8 --select=E | pygmentize -l python
    else
        flake8 | pygmentize -l python
    end
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
    ./manage.py test --parallel 8 --noinput $argv
end


function integration_tests --description 'Run core [module] integrations tests against --host [127.0.0.1:8000]'
    activate_venv
    ./manage.py integration_test $argv
end

function build --description 'Run all build steps: yarn, JS, CSS, etc'
    cd "$JS_ROOT"
    yarn; or return 1
    compjs; or return 1
    buildcss; or return 1
end

function compjs --description 'Compile a given JS file in core'
    cd "$JS_ROOT"

    check_node_dependency webpack
    webpack 2>&1 | cat
end

function watchjs --description 'Watch all given JS file in core'
    cd "$JS_ROOT"
    check_node_dependency webpack
    webpack --mode development --watch --info-verbosity verbose
end

function buildcss --description 'Compile all Sass files in core'
    cd "$JS_ROOT"
    check_node_dependency node-sass-chokidar

    echo $blue"[*] Compiling"$normal" scss files"$normal

    node-sass-chokidar scss/ -o ../static/css 2>&1 | cat
end

function watchcss --description 'Watch all Sass files in core'
    cd "$JS_ROOT"
    check_node_dependency node-sass-chokidar

    node-sass-chokidar scss/ -o ../static/css/ --watch --skip-initial
end

function resetdb --description 'Empty and reset the local database (DESTROYS ALL DATA!)'
    activate_venv
    echo 'HIT CTRL+C to cancel db drop -- you have 2 seconds... buddy...'
    sleep 2.5
    echo 'buddy you missed your chance, deleting everything'
    dropdb oddslingers
    createdb oddslingers
    redis-cli FLUSHALL
    ./manage.py migrate
    ./manage.py create_admins
end

function fetchdb --description 'Pull and load the database from a remote [host]'
    echo "[1/5] Saving local db $POSTGRES_DB to $DATA_DIR/backups/$POSTGRES_DB_"(date +%s)".sql.gz..."
    set local_dump (backup | tail -1 | tr -d '\r')

    echo "[2/5] Backing up remote db $argv[1]:$POSTGRES_DB to $argv[1]:/opt/oddslingers.poker/data/backups/$POSTGRES_DB_<ts>.sql.gz..."
    set dump_file (ssh $argv[1] /opt/oddslingers.poker/bin/oddslingers-server backup | tail -1 | tr -d '\r')
    
    echo "[3/5] Downloading $argv[1]:/opt/oddslingers.poker to localhost:/tank/$argv[1]..."
    mkdir -p /tank/$argv[1]/data/backups
    rsync -r --archive --info=progress2 --exclude=database --exclude=backups $argv[1]:/opt/oddslingers.poker/ /tank/$argv[1]
    rsync -r --archive --info=progress2 $argv[1]:"$dump_file" /tank/$argv[1]/data/backups

    set gz_file /tank/$argv[1]/data/backups/(basename "$dump_file")
    echo "[4/5] Unzipping $gz_file..."
    ls $gz_file; or return 1
    gunzip $gz_file
    set sql_file /tank/$argv[1]/data/backups/(basename -s .gz "$gz_file")
    echo "[4/5] Loading $sql_file into localhost:$POSTGRES_DB database..."
    load_backup "$sql_file"
    echo "    To see more debug dumps, logs, etc from $argv[1], open /tank/$argv[1]"
end

function backup --description 'Dump a local db backup to /data/backups'
    mkdir -p "$DATA_DIR/backups"
    set dump_file "$DATA_DIR/backups/oddslingers_"(date +%s)".sql.gz"
    echo $green"[>] Backing up DB $POSTGRES_DB to $normal"(basename $dump_file)"..."
    pg_dump "$POSTGRES_DB" | gzip -9 > "$dump_file"
    echo "$dump_file"
end

function load_backup --description 'Load a [oddslingers.sql] backup into the database'
    stop
    echo '[!] Destroying database "oddslingers" in 5 sec...'
    sleep 5
    dropdb "$POSTGRES_DB"
    createdb "$POSTGRES_DB"
    psql "$POSTGRES_DB" < $argv[1]
    redis-cli FLUSHALL
    echo "[√] Destroyed database localhost:oddslingers and loaded new db from $argv[1]"
end

function deploy --description 'Deploy the current branch to beta or prod'
    if test (count $argv) -gt 0
        set server "$argv[1]"
    else
        echo "You must specify a server [beta|prod] to deploy to."
        return 1
    end
    set branch (_git_branch_name)
    
    deploy_step echo "------------------------------------------------------------------ "
    deploy_step echo $green"[+] Starting deploy process of branch $branch to oddslingers-$server ("(date)")...$normal"
    deploy_step echo "    1. lintpy & lintjs"
    deploy_step echo "    2. compjs & compcss"
    deploy_step echo "    3. makemigrations"
    deploy_step echo "    4. commit staticfiles & migrations"
    deploy_step echo "    5. push $branch -> origin/$server"
    deploy_step echo "    6. oddslingers-server deploy"
    deploy_step echo ""
    deploy_step echo "Output is logged to data/logs/deploys.log on both local and server"
    deploy_step echo "------------------------------------------------------------------"

    deploy_step echo $green"[1] Running lintpy and lintjs..."$normal
    deploy_step lintpy; or return 1
    deploy_step lintjs; or return 1

    deploy_step echo $green"[2] Building staticfiles for JS and CSS..."$normal
    deploy_step yarn; or return 1
    compjs; or return 1
    deploy_step buildcss; or return 1

    deploy_step echo $green"[3] Creating any missing migrations and merge migrations..."$normal
    deploy_step manage makemigrations; or return 1
    deploy_step manage makemigrations --merge; or return 1
    
    deploy_step echo $green"[4] Committing staticfiles and migrations..."$normal
    cd "$PY_ROOT"
    deploy_step git add static
    deploy_step git commit --allow-empty -m "staticfiles for deploy"

    deploy_step echo $green"[5] Pushing branch $branch to origin/$server..."$normal
    if [ "$branch" != "$server" ]
        deploy_step git branch -D "$server"
        deploy_step git checkout -b "$server"
    end
    deploy_step git push -f --set-upstream origin "$server"

    deploy_step echo $green"[6] Deploying $branch to oddslingers-$server now..."$normal
    if quiet which brew
        unbuffer ssh -t "oddslingers-$server" "oddslingers-server deploy $server" 2>&1 | sed -l 's/^/     /' | unbuffer -p tee -a "$DATA_DIR/logs/deploys.log"
    else 
        unbuffer ssh -t "oddslingers-$server" "oddslingers-server deploy $server" 2>&1 | sed -u 's/^/     /' | unbuffer -p tee -a "$DATA_DIR/logs/deploys.log"
    end
    
    deploy_step git checkout $branch
    deploy_step echo $green"[√] Deployed $branch to origin/$server:$blue oddslingers-$server"$normal
end

function yarn_install --description 'Install yarn packages'
    cd "$JS_ROOT"
    yarn install
end

### General Helper Functions ###

# Pretty Colors
set -x TERM xterm-256color
set arrow "➜ "
if set_color normal
    set cyan (set_color -o cyan)
    set green (set_color -o green)
    set yellow (set_color -o yellow)
    set purple (set_color -o magenta)
    set red (set_color -o red)
    set blue (set_color -o blue)
    set black (set_color -o black)
    set white (set_color -o white)
    set normal (set_color normal)
else
    set cyan ""
    set green ""
    set yellow ""
    set purple ""
    set red ""
    set blue ""
    set black ""
    set white ""
    set normal ""
end

function quiet --description 'Run a command with all stdout and stderr silenced'
    if not count $argv > /dev/null
        return 0
    end

    # quote every argument so spacing is preserved
    set evalstr (string escape -- $argv)
    # eval the command with output silenced
    eval "$evalstr 2>&1 > /dev/null" 2>&1 > /dev/null; and return 0; or return 1
end

function deploy_step --description 'Indent all output by one tab and log to file'
    switch "$argv[1]"
        case 'echo'
            eval (string escape -- $argv) 2>&1 | tee -a "$DATA_DIR/logs/deploys.log"
        case '*'
            if quiet which brew
                eval (string escape -- $argv) 2>&1 | sed -l 's/^/     /' | unbuffer -p tee -a "$DATA_DIR/logs/deploys.log"
            else
                eval (string escape -- $argv) 2>&1 | sed -u 's/^/     /' | unbuffer -p tee -a "$DATA_DIR/logs/deploys.log"
            end
    end
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
	bash -c "fish -c 'source \"""$ROOT""\"/bin/oddslingers.fish; ""$argv""' &"
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

    # send result to stdout or return 1
    not test $results; and return 1
    echo "$results"
end

function _git_branch_name --description 'Get the current git branch name'
    echo (git symbolic-ref HEAD ^/dev/null | sed -e 's|^refs/heads/||')
end

function activate_venv --description 'Activate the core virtual environment'

    if [ "$IS_DOCKER" ]
        cd "$ROOT"
        source .venv-docker/bin/activate.fish
        cd "$PY_ROOT"
    else
        cd "$PY_ROOT"
        if [ "$VIRTUAL_ENV" ]
            if not echo "$VIRTUAL_ENV" | grep -q "core/.venv"
                echo $red"[!] Active virtualenv must be located at core/.venv"$normal
                return 1
            end
            quiet functions -c fish_prompt _old_fish_prompt
            quiet source "$VIRTUAL_ENV"/bin/activate.fish
        else
            source .venv/bin/activate.fish
        end

        if not test -d .venv
            echo $red"[!] Virtualenv must be present in core/.venv"$normal
            return 1
        end
    end

    set PYTHON_BIN (which python)

    if not python -c 'import django; print(f"Django v{django.__version__}")' > /dev/null
        echo "[!] Failed to run python, is your virtualenv setup properly in core/.venv?"
        echo "PYTHONPATH: $PYTHONPATH"
        echo "PYTHON BIN: $PYTHON_BIN"
        echo "VIRTUAL_ENV: $VIRTUAL_ENV"
        return 1
    end
    # echo "[√] Activated .venv: "(which python) (python --version)
end

function check_node_dependency
    cd "$JS_ROOT"
    which $argv | grep -q "node_modules/.bin/"
    or begin
        echo "Could not find '$argv' command, did you run `yarn` and is ./node_modules/.bin in your \$PATH?"
        return 1
    end
end

function check_python_dependency
    if [ "$IS_DOCKER" ]
        cd "$ROOT"
        which $argv | grep -qE ".venv-docker/bin/"
        or begin
            echo "Could not find '$argv' command, did you run `pip install -r requirements.txt` and is your virtualenv in core/.venv-docker activated?"
            return 1
        end
    else
        cd "$PY_ROOT"
        which $argv | grep -qE "core/.venv/bin/"
        or begin
            echo "Could not find '$argv' command, did you run `pip install -r requirements.txt` and is your virtualenv in core/.venv activated?"
            return 1
        end
    end
end


function find_js_page
    set basefilename (basename "$argv[1]")
    set js_src (find_file "$basefilename" $JS_ROOT"/pages/")
    if not test "$js_src"
        echo $red"[X] JS page not found: $basefilename"$normal
        return 1
    end
    echo $js_src
end
