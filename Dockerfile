# Main image for running things in a Django/Python environment.
#
# Usage:
#    docker-compose run django gunicorn --bind 0.0.0.0:8080 projectname.wsgi:application
#    docker-compose run django ./manage.py migrate
#    docker-compose run django ./manage.py shell_plus
#    docker-compose run django ./manage.py ...

# Debian-based image is faster than alpine because it can install pip wheels
FROM python:3.12-bookworm

# Configuration defaults
ENV ODDSLINGERS_ROOT "/opt/oddslingers.poker"
ENV DATA_DIR "$ODDSLINGERS_ROOT/data"
ENV HTTP_PORT "8000"
ENV DJANGO_USER "www-data"
ENV VENV_NAME ".venv-docker"
ENV NODE_MAJOR "18"

# Setup system environment variables neded for python to run smoothly
ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1

ENV PYTHONUNBUFFERED 1

# Install system requirements
RUN apt-get update && apt-get install -y \
    # psycopg2 requirements
    libpq-dev \
    # fish shell
    fish \
    # npm
    npm \
    # gosu
    gosu \
    # Needed for compiled C extension packages (psycopg2, cryptography, etc.)
    build-essential \
    # python requirements
    python3-dev python3-pip python3-venv jq \
    # supervisor
    supervisor && \
    # cleanup apt caches to keep image small
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/apt/keyrings
RUN curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
RUN echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list
RUN apt-get update && apt-get install -y nodejs

# No virtualenv needed — the Docker container IS the isolation layer.
# System site-packages at /usr/local/lib/python3.12 are not overwritten by
# volume mounts (./core, ./data, ./bin, ./env) so there is no venv/host conflict.

WORKDIR "$ODDSLINGERS_ROOT"
ENV PATH="${ODDSLINGERS_ROOT}/bin:./node_modules/.bin:${PATH}"

# Add .git HEAD to container 
ADD .git/HEAD ./.git/HEAD
ADD .git/refs/heads/ ./.git/refs/heads/

# Install Python dependencies.
# requirements.lock is the pinned lockfile generated from core/requirements.txt via:
#   uv pip compile --python-version 3.12 --python-platform linux core/requirements.txt -o core/requirements.lock
# Regenerate with: python3 bin/gen-requirements.py core/Pipfile > core/requirements.txt && uv pip compile ...
COPY ./core/requirements.lock /tmp/requirements.lock
RUN pip install --upgrade pip setuptools && \
    pip install --no-cache-dir -r /tmp/requirements.lock && \
    rm /tmp/requirements.lock
RUN npm install --global npm && npm install --global yarn
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
