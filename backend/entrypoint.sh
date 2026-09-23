#!/bin/sh
set -eu

alembic upgrade head

if [ "${SEED_DATA:-false}" = "true" ]; then
    python -m app.seed
fi

exec "$@"
