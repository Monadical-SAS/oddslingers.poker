# Main image for running things in a Django/Python environment.
#
# Usage:
#    docker-compose run django gunicorn --bind 0.0.0.0:8080 projectname.wsgi:application
#    docker-compose run django ./manage.py migrate
#    docker-compose run django ./manage.py shell_plus
#    docker-compose run django ./manage.py ...

# Debian-based image is faster than alpine because it can install pip wheels
# Downgraded to 3.7 https://github.com/python/typed_ast/issues/124 
# ref1: https://github.com/python/mypy/issues/7001
# ref2: https://github.com/dbader/pytest-mypy/pull/44
FROM python:3.7-buster

# Configuration defaults
ENV ODDSLINGERS_ROOT "/opt/oddslingers.poker"
ENV DATA_DIR "$ODDSLINGERS_ROOT/data"
ENV HTTP_PORT "8000"
ENV DJANGO_USER "www-data"
ENV VENV_NAME ".venv-docker"

# Setup system environment variables neded for python to run smoothly
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

# Install system requirements
RUN apt-get update && apt-get install -y \
    # psycopg2 requirements
    python-psycopg2 libpq-dev \
    # fish shell
    fish \
    # npm
    npm \
    # gosu
    gosu \
    # Needed for typed-ast dependency
    build-essential \
    # python requirements
    python3-dev python3-pip python3-venv jq \
    # supervisor
    supervisor && \
    # cleanup apt caches to keep image small
    rm -rf /var/lib/apt/lists/*

# Setup Python virtualenv separately from code dir in /opt/oddslingers/.venv-docker.
#   It needs to be outside of the code dir because the code is mounted as a volume
#   and would overwite the docker-specific venv with the incompatible host venv.

WORKDIR "$ODDSLINGERS_ROOT"
RUN pip install virtualenv && \
    virtualenv "$VENV_NAME"
ENV PATH="$ODDSLINGERS_ROOT/$VENV_NAME/bin:${ODDSLINGERS_ROOT}/bin:./node_modules/.bin:${PATH}"

# Add .git HEAD to container 
ADD .git/HEAD ./.git/HEAD
ADD .git/refs/heads/ ./.git/refs/heads/

# Install the python dependencies from requirements.txt into /opt/oddslingers.poker/.venv-docker.
COPY ./core/Pipfile.lock "$ODDSLINGERS_ROOT/Pipfile.lock"
RUN jq -r '.default,.develop | to_entries[] | .key + .value.version' "$ODDSLINGERS_ROOT/Pipfile.lock" | \
    pip install --no-cache-dir -r /dev/stdin && \
    rm "$ODDSLINGERS_ROOT/Pipfile.lock"
RUN npm install --global npm yarn
RUN userdel "$DJANGO_USER" && addgroup --system "$DJANGO_USER" && \
    adduser --system --ingroup "$DJANGO_USER" --shell /bin/false "$DJANGO_USER"

# Workers require to write data and own the directory
RUN mkdir "$ODDSLINGERS_ROOT/data"
RUN mkdir "$ODDSLINGERS_ROOT/data/logs"
RUN mkdir -p "$ODDSLINGERS_ROOT/core/js/node_modules"
RUN chown "$DJANGO_USER"."$DJANGO_USER" "$ODDSLINGERS_ROOT/data"
RUN chown -R "$DJANGO_USER"."$DJANGO_USER" "$ODDSLINGERS_ROOT/data/logs"
RUN chown -R "$DJANGO_USER"."$DJANGO_USER" "$ODDSLINGERS_ROOT/core"

ENTRYPOINT [ "/opt/oddslingers.poker/bin/entrypoint.sh" ]
