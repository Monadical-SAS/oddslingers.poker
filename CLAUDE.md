<!-- wfc:start -->
# WFC — oddslingers.poker

## Project

Personal poker platform. Python + Django backend, React + Redux frontend.
No live users. Modernization in progress (see `~/.wfc/projects/oddslingers.poker/`).

## Always Do

- Use `wfc git <cmd>` for all git operations (never bare `git`)
- Use `wfc test` to run tests
- Use `make quality-check` before committing
- Write plan artifacts to `~/.wfc/projects/oddslingers.poker/branches/<branch>/`
- Use `docker-compose run --rm django` to run management commands

## When

| Situation | Command |
|-----------|---------|
| Run tests | `wfc test` or `make test` |
| Format code | `make format` |
| Lint | `make lint` |
| Start services | `docker-compose up -d postgres redis` |
| Build Django image | `docker-compose build django` |
| Django shell | `docker-compose run --rm django ./manage.py shell_plus` |
| Run migrations | `docker-compose run --rm django ./manage.py migrate` |

## Never Do

- Push to remote without explicit user request
- Modify `.venv-docker/` or `core/static/` directly
- Run `pip install` outside Docker — use Pipfile + Docker build
- Commit `Pipfile.lock` changes without running `pipenv lock` inside the container

## Stack

| Layer | Current | Target |
|-------|---------|--------|
| Python | 3.7 (EOL) | 3.12 |
| Django | 2.2.11 | 4.2 LTS |
| React | 16.6.3 | 18 |
| Postgres | 12 (dev) | 16 |
| Redis | 5 | 7 |

## Modernization Plan

Active plan: `~/.wfc/projects/oddslingers.poker/branches/main/plans/plan_stack_modernization_20260408_155858/`

Phases:
1. **Phase 1** (O-001–O-012): Infra bumps + Python 3.12 Dockerfile/Pipfile prep
2. **Phase 1.5**: Fix pip-level blockers (gevent, greenlet, msgpack, asgiref, psycopg2)
3. **Phase 2**: Django 4.2 + Channels 3 + Daphne 4 upgrade
4. **Phase 3**: React 18 + Webpack 5

## Skill Quick Reference

| Task | Skill |
|------|-------|
| Plan a phase | `/wfc-plan` |
| Execute plan | `/wfc-implement` |
| Code review | `/wfc-review` |
| Prioritize work | `/wfc-prioritize` |
| Deepen a plan | `/wfc-deepen` |

<!-- wfc:end -->
