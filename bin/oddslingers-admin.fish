# #!/usr/bin/env fish

set REPO_DIR /opt/oddslingers

### Prod Helpers ###

function remote --description 'Run ssh command on remote server [command]'
    ssh -t $ODDSLINGERS_DOMAIN $argv
end

function notify --description 'Post tracking notification to zulip'
    cd $REPO_DIR"/core"
    source $REPO_DIR"/.venv/bin/activate.fish"
    env ODDSLINGERS_ENV='PROD' ./manage.py track_analytics_event $argv
end

function checkstatus --description 'Confirm that prod is returning a 200 status'
    set site_status (curl -s -o /dev/null -w "%{http_code}" https://$ODDSLINGERS_HOST)
    test $site_status = 200
    and echo $green"[√] Confirmed https://$ODDSLINGERS_HOST is up ($site_status)."
    and return 0
    echo $red"[!] GET failed:"$normal" https://$ODDSLINGERS_HOST is returning HTTP $site_status"
    return 1
end

function deploy --description 'Deploy current branch to the oddslingers server, run migrations and restart runserver'
    cd $GRATER_PATH"/core"
    set -l git_branch (_git_branch_name)
    set -l username (whoami)
    set -l hostname (hostname)

    echo $yellow"[↑] Pushing"$normal" $git_branch to origin/live branch"
    git push origin "$git_branch":live --force

    remote "source /opt/oddslingers.poker/prod_commands.fish; \
          oddslingers.notify 'Deploy of `$git_branch` -> `origin/live` started by $username@$hostname'; \
          oddslingers.update; \
          source /opt/oddslingers.poker/prod_commands.fish; \
          oddslingers.setup; \
          oddslingers.stop; \
          oddslingers.migrate; \
          oddslingers.start;\
          date; \
          oddslingers.notify 'Deploy finished: $ODDSLINGERS_HOST'"

    sleep 3
    checkstatus
end

function deploystatic --description 'Deploy current branch to the oddslingers server without reloading python or migrating'
    cd $GRATER_PATH"/core"
    set -l git_branch (_git_branch_name)
    set -l username (whoami)
    set -l hostname (hostname)

    echo $yellow"[↑] Pushing"$normal" $git_branch to origin/live branch"
    git push origin "$git_branch":live --force

    remote "source /opt/oddslingers.poker/prod_commands.fish;\
          oddslingers.notify 'Deploy of `$git_branch` -> `origin/live` (staticfiles only) started by $username@$hostname'; \
          oddslingers.update;\
          supervisorctl stop httpworker1; \
          supervisorctl start httpworker1; \
          supervisorctl stop httpworker2; \
          supervisorctl start httpworker2; \
          date; \
          oddslingers.notify 'Deploy finished: $ODDSLINGERS_HOST'"

    sleep 1
    checkstatus
end

function fetchproddb --description 'Get a SQL dump of the prod database'
    echo $yellow"[>] Dumping $ODDSLINGERS_HOST DB to file > "$normal"/tmp/prod_backup.sql"

    remote "cd /tmp; \
                                      pg_dump oddslingers > prod_backup.sql; \
                                      rm -f prod_backup.sql.zip; \
                                      zip prod_backup.sql.zip prod_backup.sql;"

    echo $green"[↓] Downloading prod db dump "$normal"prod_backup.sql"
    scp $ODDSLINGERS_HOST:/tmp/prod_backup.sql.zip prod_backup.sql.zip
end

function loaddb --description 'Overwrite the local db with a SQL dump [file.sql]'
    if not test -e "$argv"
        echo $red"[X] Please specify a SQL file to load, e.g. prod_backup.sql"$normal
        return 1
    end
    echo $red"[*] Overwriting local oddslingers db with "$normal"$argv"$red" in 5 sec... (press Ctrl+C to cancel)"$normal
    sleep 5

    dropdb oddslingers
    and createdb oddslingers
    and psql oddslingers < $argv > /dev/null
    and echo $green"[√] Loaded $argv into local oddslingers db"$normal" (www-data & root GRANT errors can be safely ignored)"
    or echo $red"[X] Failed to load $argv DB dump"$normal
end

function loadproddb --description 'Get a SQL dump of the prod database and load it into the local dev db'
    fetchproddb
    unzip prod_backup.sql.zip
    loaddb prod_backup.sql
end
