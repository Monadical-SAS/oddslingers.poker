#!/usr/bin/env fish

### CONFIG VARS ###
set HOSTNAME (hostname)
set REPO_DIR (cd (dirname (status -f)); cd ..; and pwd)
set DATA_DIR "$REPO_DIR/data"
set PY_ROOT "$REPO_DIR/core"
set JS_ROOT "$REPO_DIR/core/js"
set REPO_URL "https://github.com/monadical-sas/oddslingers.poker"
set DJANGO_USER "www-data"
if [ "$POSTGRES_DB" ]
    set POSTGRES_DB "$POSTGRES_DB"
else
    set POSTGRES_DB "oddslingers"
end

switch "$HOSTNAME"
    case 'oddslingers-prod'
        set -x ODDSLINGERS_ENV "PROD"
    case 'oddslingers-prod-bulk'
        set -x ODDSLINGERS_ENV "PROD"
    case 'oddslingers-beta'
        set -x ODDSLINGERS_ENV "BETA"
    case 'oddslingers-beta-bulk'
        set -x ODDSLINGERS_ENV "BETA"
    case 'plum'
        set -x ODDSLINGERS_ENV "PROD"
    case '*'
        echo "oddslingers-server cmd should only be run on PROD or BETA servers."
        exit 1
end

### Prod Functions ###

function start --description 'Start all production services'
    echo $blue"[+] Starting server processes..."$normal
    chowndirs

    systemctl stop postgresql
    systemctl stop redis-server
    systemctl stop nginx
    systemctl stop cron
    systemctl start supervisor
    supervisorctl reread
    supervisorctl update
    supervisorctl start all

    sleep 2
    echo $green"[√] Oddslingers web stack started"$normal
    supervisorctl status
end

function stop --description 'Stop all production services'
    echo $red"[X] Stopping all services..."$normal
    stop_heartbeats
    supervisorctl stop oddslingers-django:
    supervisorctl stop oddslingers-bg:
end

function stop_heartbeats --description 'Kill all the table heartbeat processes running on production'
    while psax python | grep table_heartbeat
        for pid in (psax table_heartbeat | awk '{print $1}')
            kill $pid
            echo $red"[X] Killed Table Heartbeat $pid"$normal
        end
        sleep 2
    end
end

function manage --description 'Run manage.py [cmd] [args] e.g. migrate'
    switch "$argv[1]"
        case 'shell'
            echo 'Use the `oddslingers-server shell` command instead.'
            return 1
        case 'shell_plus'
            echo 'Use the `oddslingers-server shell` command instead.'
            return 1
        case '*'
	    if [ "$IS_DOCKER" ]
		cd "$PY_ROOT"
                bash -c "source $REPO_DIR/.venv-docker/bin/activate; env CONNECTION_STR='$CONNECTION_STR' ./manage.py $argv"
            else
                cd "$PY_ROOT"
                sudo -u $DJANGO_USER bash -c "source .venv/bin/activate; env CONNECTION_STR='$CONNECTION_STR' ./manage.py $argv"
	    end
    end
end

function shell --description 'Open the production django shell_plus'
    cd "$PY_ROOT"
    if [ "$IS_DOCKER" ]
        bash -c "source .venv/bin/activate; env DJANGO_DEBUG_HELPERS=1 IPYTHONDIR=/data/.ipython CONNECTION_STR='$CONNECTION_STR' PYTHONSTARTUP=$PY_ROOT/oddslingers/save_ipython_history.py ./manage.py shell_plus $argv"
    else
        sudo -u $DJANGO_USER bash -c "source .venv/bin/activate; env DJANGO_DEBUG_HELPERS=1 IPYTHONDIR=/data/.ipython CONNECTION_STR='$CONNECTION_STR' PYTHONSTARTUP=$PY_ROOT/oddslingers/save_ipython_history.py ./manage.py shell_plus $argv"
    end
end

function migrate --description 'Run migrations on the production db'
    manage migrate
end

function setup --description 'Run the commands which set up the server and install apt dependencies'
    activate_venv
    cd "$PY_ROOT"
    pip install -q -r requirements.txt  #  --no-deps --require-hashes 

    chowndirs
end

function update --description 'Pull a fresh copy of the specified [branch] to the server'
    if test (count $argv) -gt 0
        set branch "$argv[1]"
    else
        echo "You must specify a git [branch] to update from."
        exit 1
    end
    echo $blue"[↓] Pulling"$normal" origin/$branch to $HOSTNAME $REPO_DIR"
    cd "$PY_ROOT"
    git remote update; or return 1
    quiet git branch -D temp -q
    git checkout -b temp -q; or return 1
    git branch -D $branch -q; or return 1
    git checkout -f $branch -q; or return 1
end


function offsite_backup --description 'Backup and save files to remote [host]'
    if not test (count $argv) -eq 1
        echo "You must specify a [hostname] to rsync the backup to."
        exit 1
    end
    backup
    echo $green"[>] Syncing backup of /opt/oddslingers.poker/ to $argv[1]:"$normal"/tank/$HOSTNAME"...
    rsync -r --archive --stats --bwlimit=10000 --exclude=database /opt/oddslingers.poker/ $argv[1]:/tank/$HOSTNAME
end

function backup --description 'Dump a production db backup to /data/backups'
    mkdir -p "$DATA_DIR/backups"
    set dump_file "$DATA_DIR/backups/oddslingers_"(date +%s)".sql.gz"
    
    echo $green"[>] Backing up DB $POSTGRES_DB to $normal"(basename $dump_file)"..."
    sudo -u postgres pg_dump "$POSTGRES_DB" | gzip -9 > "$dump_file"

    echo "$dump_file"
end

function load_backup --description 'Load a [oddslingers.sql] backup into the database'
    switch "$ODDSLINGERS_ENV"
        case 'PROD'
            echo "[X] You must do this manually on prod, as it is dangerous!"
        case '*'
            stop
            echo "[!] Destroying database $HOSTNAME:$POSTGRES_DB in 5 sec..."
            sleep 5
            dropdb "$POSTGRES_DB"
            createdb "$POSTGRES_DB"
            psql "$POSTGRES_DB" < $argv[1]
            redis-cli FLUSHALL
            echo "[√] Destroyed database $HOSTNAME:$POSTGRES_DB and loaded new db from $argv[1]"
    end
end

function notify --description 'Post a notification to the zulip #logs stream'
    activate_venv
    cd "$PY_ROOT"
    manage track_analytics_event -s logs -t Deploys "'$argv'"
end

function clear_caches --description 'Clear CND edge caches, e.g. cloudflare'
    source_env $REPO_DIR/env/secrets.env
    curl -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/purge_cache" \
     -H "X-Auth-Email: $CLOUDFLARE_EMAIL" \
     -H "X-Auth-Key: $CLOUDFLARE_KEY" \
     -H "Content-Type: application/json" \
     --data '{"purge_everything":true}'
    or "Failed to clear caches, are CLOUDFLARE_EMAIL and CLOUDFLARE_KEY set in env/secrets.env?"
end

function chowndirs --description 'Set the correct permissions on the data dirs'
    chown $DJANGO_USER:$DJANGO_USER "$DATA_DIR"
    chown -R root:root "$DATA_DIR/certs"
    chown -R postgres:postgres "$DATA_DIR/database"
    chown -R $DJANGO_USER:$DJANGO_USER "$DATA_DIR/logs"
    chown -R $DJANGO_USER:$DJANGO_USER "$DATA_DIR/newsletters"
    chown -R $DJANGO_USER:$DJANGO_USER "$DATA_DIR/geoip"
    chown -R $DJANGO_USER:$DJANGO_USER "$DATA_DIR/debug_dumps"
    chown -R $DJANGO_USER:$DJANGO_USER "$DATA_DIR/caches"
    chown $DJANGO_USER:$DJANGO_USER "$DATA_DIR/support_tickets"
end


function setup_tunnels --description 'Setup stunnels between necessary servers'
    echo "This command does several steps to setup stunnels between our servers."
    echo ""
    echo "Server:"
    echo "1. generate /etc/stunnel/passwords.txt with PSKs"
    echo "2. start stunnel with supervisord"
    echo "3. open ports 8432, 8379"
    echo "4. test to make sure clients can connect"
    echo ""
    echo "Client:"
    echo "1. define server hosts in /etc/hosts"
    echo "2. copy PSK from server to client"
    echo "3. start stunnel with supervisord"
    echo "4. test to make sure clients can connect"
    echo "--------------------"
    echo ""
    read -P "Is this the client or the server? [client/server]" server
    switch $server
        case 'server'
            read -P "1. Input a secure, random password to put in /etc/stunnel/passwords.txt: " psk
            echo "oddslingers:$psk" > /etc/stunnel/passwords.txt
            chmod 600 /etc/stunnel/passwords.txt

            echo "2. Starting stunnel with supervisord"
            systemctl stop redis-server
            systemctl stop postgres
            supervisorctl reread
            supervisorctl update
            supervisorctl restart oddslingers-base:postgres-tunnel
            supervisorctl restart oddslingers-base:redis-tunnel

            echo "3. Allowing incoming stunnel connections to 8432 and 8379"
            ufw allow 8432
            ufw allow 8379
            set pubip (dig -4 +short myip.opendns.com @resolver1.opendns.com)

            echo "3. Test to make sure connections are allowed on $pubip:8432 and 8379"
            supervisorctl status
            echo "√ Success! Now run setup_tunnels on the client."

        case 'client'
            echo "Make sure you've run setup_tunnels on the server you want to connect to first."
            
            read -P "1. Input the server's IP address: " serverip
            echo "$serverip redis postgres" >> /etc/hosts

            read -P "2. Input the same secure, random password in /etc/stunnel/passwords.txt on the server: " psk
            echo "oddslingers:$psk" > /etc/stunnel/passwords.txt
            chmod 600 /etc/stunnel/passwords.txt

            echo "2. Starting stunnel with supervisord"
            systemctl stop redis-server
            systemctl stop postgres
            supervisorctl reread
            supervisorctl update
            supervisorctl restart oddslingers-base:postgres-tunnel
            supervisorctl restart oddslingers-base:redis-tunnel

            echo "3. Test to make sure connections are allowed on localhost:5432 and 6379"
            redis-cli -p 6379 ping
            pg_isready -h 127.0.0.1 -p 5432
            echo "√ Success!"
        case '*'
            echo 'Must be one of: client or server'
            return 1
    end
end


function deploy --description 'Use deploy function instead of this'
    if test (count $argv) -gt 0
        set branch "$argv[1]"
    else
        echo "You must specify a git [branch] to deploy."
        return 1
    end

    wall "Deploy of $argv[1] to $HOSTNAME started by $REMOTEUSER... (output is logged to $DATA_DIR/logs/deploys.log)"
    deploy_step echo "-------------------------------------------------------------------------------"
    deploy_step echo $green"[+] Starting server deploy process of branch $branch to $HOSTNAME ("(date)")..."$normal
    deploy_step echo "    1. check for active users playing on site"
    deploy_step echo "    2. pull origin/$branch to local"
    deploy_step echo "    3. install pip requirements and update configs"
    deploy_step echo "    4. stop django processes"
    deploy_step echo "    5. run database migrations"
    deploy_step echo "    6. start django processes"
    deploy_step echo "    7. update caches"
    deploy_step echo ""
    deploy_step echo "Output is logged to data/logs/deploys.log on both local and server"
    deploy_step echo "-------------------------------------------------------------------------------"
   
    deploy_step echo $green"[1] Checking for active users playing on the site..."$normal
    if not quiet manage active_sessions
        deploy_step echo $yellow"[!] There are currently active users playing games, are you sure you want to deploy? Press CTRL+C to cancel. (Continuing in 5sec...)"$normal
        deploy_step manage active_sessions
        sleep 6
    end

    deploy_step echo $green"[2] Pulling origin/$branch to local code directory..."$normal
    deploy_step update "$branch"; or return 1
    deploy_step cd "$PY_ROOT"
    set commitid (git rev-parse --short "$branch")
    set commitmsg (git show -s --format=%s "$branch")
    deploy_step notify "
---
:building_construction: "'**'"Starting deploy of origin/$branch to $HOSTNAME by"'** @**'"$REMOTEUSER"'**.'"
origin/$branch: [`$commitid`]($REPO_URL/commit/$commitid) "'*'"$commitmsg"'*'

    deploy_step echo $green"[3] Installing pip requirements and updating configs..."$normal
    deploy_step setup; or return 1

    deploy_step echo $green"[4] Stopping all django processes..."$normal
    deploy_step stop; or return 1

    deploy_step echo $green"[5] Running database migrations..."$normal
    deploy_step migrate; or return 1

    deploy_step echo $green"[6] Starting all django processes..."$normal
    deploy_step start; or return 1

    deploy_step echo $green"[7] Updating local caches and clearing cloudflare cache..."$normal
    deploy_step manage save_leaderboard_cache
    deploy_step clear_caches

    deploy_step date
    set pubip (dig -4 +short myip.opendns.com @resolver1.opendns.com)
    deploy_step notify ":heavy_check_mark:  "'**'"Finished deploy of origin/$branch to $HOSTNAME."'**'"
Confirm it works [https://$HOSTNAME](http://$pubip)"
    deploy_step echo $green"[√] Deployed origin/$branch to:$blue $HOSTNAME"$normal
end


### General Helper Functions ###




# Pretty Colors
set -x TERM xterm-256color
set -x arrow "➜ "
if set_color normal
    set -x cyan (set_color -o cyan)
    set -x green (set_color -o green)
    set -x yellow (set_color -o yellow)
    set -x purple (set_color -o magenta)
    set -x red (set_color -o red)
    set -x blue (set_color -o blue)
    set -x black (set_color -o black)
    set -x white (set_color -o white)
    set -x normal (set_color normal)
else
    set -x cyan ""
    set -x green ""
    set -x yellow ""
    set -x purple ""
    set -x red ""
    set -x blue ""
    set -x black ""
    set -x white ""
    set -x normal ""
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

function faketty
    unbuffer -p $argv
end

function psax --description 'Filter ps ax output for a specified string'
    ps ax -o pid,command | grep -v grep | grep --color=always -i "$argv"
end

function pid --description 'get the best guess for the pid of a process'
    psax "$argv" | awk '{print $1}'
end

function _git_branch_name --description 'Get the current git branch name'
    echo (git symbolic-ref HEAD ^/dev/null | sed -e 's|^refs/heads/||')
end

function fish_prompt
    set_color red; echo -n $USER
    set_color normal; echo -n '@'
    set_color blue; echo -n $HOSTNAME
    set_color normal; echo -n ':'
    set_color green; echo -n (pwd | sed "s,^$HOME,~,")
    set_color normal; echo -n '$ '
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
                exit 1
            end
            quiet functions _old_fish_prompt; or functions -c fish_prompt _old_fish_prompt
            source "$VIRTUAL_ENV"/bin/activate.fish
        else 
            source .venv/bin/activate.fish
        end

        if not test -d .venv
            echo $red"[!] Virtualenv must be present in core/.venv"$normal
            exit 1
        end
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

function source_env --description "Source a bash/posix style .env file"
    # e.g. source_env /opt/oddslingers.poker/env/secrets.env

    for i in (cat $argv | sed -e 's/#[^!].*$//' | awk 'NF')
        set arr (echo $i |tr = \n)
        set -gx $arr[1] "$arr[2]"
        # echo "$arr[1]"="$arr[2]"
    end
end

function deploy_step --description 'Indent all output by one tab and log to file'
    switch "$argv[1]"
        case 'echo'
            eval (string escape -- $argv) 2>&1 | tee -a "$DATA_DIR/logs/deploys.log"
        case 'manage' 'update' 'migrate' 'start' 'stop' 'clear_caches'
            # crazy nonsense to get unbuffered fish command output for long running commands
            set args (string escape -- $argv)
            bash -c "/opt/oddslingers.poker/bin/oddslingers-server $args 2>&1 | sed -u 's/^/     /' | unbuffer -p tee -a $DATA_DIR/logs/deploys.log"
        case '*'
            eval (string escape -- $argv) 2>&1 | sed -u 's/^/     /' | unbuffer -p tee -a "$DATA_DIR/logs/deploys.log"
    end
end
