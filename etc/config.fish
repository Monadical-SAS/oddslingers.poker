cd /opt/oddslingers/core

set -x fish_greeting ""
set -x PATH /opt/oddslingers/bin ./node_modules/.bin $PATH

if test -z "$ODDSLINGERS_ENV"
    echo "You must set ODDSLINGERS_ENV in /etc/environment!!"
end

set -x HOSTNAME (hostname)
set -x LOGINS_HISTORY /opt/oddslingers/data/logs/ssh.log
set -x TMUX_HISTORY /opt/oddslingers/data/logs/tmux.log
set -x FISH_HISTORY /opt/oddslingers/data/logs/fish.log
# DJANGO_SHELL_LOG path can be found in settings.DJANGO_SHELL_LOG
ln -f -s /root/.local/share/fish/fish_history /opt/oddslingers/data/logs/fish.log

set -q REMOTEUSER; or set -x REMOTEUSER "root"
set -q SSH_CONNECTION; or set -x REMOTEUSER "local fish shell"

set -x CONNECTION_STR "Logged in user: $REMOTEUSER@$HOSTNAME ($SSH_CONNECTION) at "(date)

set -x HELP_STR "
Useful commands:
    supervisorctl status
    oddslingers-server deploy [beta|prod]
    oddslingers-server shell
    oddslingers-server manage [command]
    oddslingers-server backup
    oddslingers-server help

Useful directories:
    /opt/oddslingers/data
    /opt/oddslingers/data/logs
    /opt/oddslingers/data/backups
    /opt/oddslingers/data/support_tickets

(If you dont see input or output when typing, run your command in bash instead.)

https://github.com/monadical-sas/oddslingers.poker/wiki/Production-Environment
-------------------------------------------------------------"


if set_color normal > /dev/null 2>/dev/null
    set cyan (set_color -o cyan)
    set green (set_color -o green)
    set yellow (set_color -o yellow)
    set purple (set_color -o magenta)
    set red (set_color -o red)
    set blue (set_color -o blue)
    set black (set_color -o black)
    set white (set_color -o white)
    set dark (set_color -d 589)
    set normal (set_color normal)
else
    function set_color
        true
    end
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

# Nesting order is: ssh -> fish -> tmux -> script -> fish

if test -z "$INSIDE_SCRIPT"
    if test -z "$TMUX"
        echo -e "- cmd: echo \"$CONNECTION_STR. Activity is logged to $FISH_HISTORY\" >> $LOGINS_HISTORY\n  when: "(date +%s) >> $FISH_HISTORY
        echo "$CONNECTION_STR. Activity is logged to $FISH_HISTORY" >> $LOGINS_HISTORY
    else
        echo "[+] New login:      $REMOTEUSER@$HOSTNAME ($SSH_CONNECTION) at "(date)
        echo "[>] Admin logs:     /opt/oddslingers/data/logs/ssh.log, fish.log, tmux.log, django_shell.log"
        echo "[i] System uptime: "(uptime)
        echo "[i] Disk usage:     "(df -h / | tail -n 1 | awk '{print $5}')
        echo "------------------------------------------------------------"
        echo -e "$HELP_STR"
        echo "[!] Most recent backup: "(ls -Artls /opt/oddslingers/data/backups/ | tail -n 1 | awk '{print $7,$8,$9,$10}')
        echo ""
        env INSIDE_SCRIPT=1 script -e -f -q -a $TMUX_HISTORY; and kill %self
    end

    if status --is-login
        set PPID (echo (ps --pid %self -o ppid --no-headers) | xargs)
        if ps --pid $PPID | grep ssh
            tmux has-session -t $HOSTNAME; and tmux attach-session -t $HOSTNAME; or tmux new-session -s $HOSTNAME; and kill %self
            echo "tmux failed to start; using plain fish shell"
        end
    end
end
