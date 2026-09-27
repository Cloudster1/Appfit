#!/bin/sh
set -e
appfit wait-for-db
# Safe with several replicas: migrations take a database lock (alembic/env.py).
alembic upgrade head
exec "$@"
