#!/bin/sh
set -eu
: "${DB_RUNTIME_PASSWORD:?required}"
: "${DB_MIGRATION_PASSWORD:?required}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file /bootstrap/bootstrap.sql
