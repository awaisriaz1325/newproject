#!/usr/bin/env bash
# Create roles and a database. Usage: infra/db/create_db.sh <dbname> (needs superuser PG* env).
set -euo pipefail
DB="${1:-compback}"
psql -v ON_ERROR_STOP=1 -f "$(dirname "$0")/bootstrap.sql"
psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB}'" | grep -q 1 || \
  psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${DB}\" OWNER compback_owner"
psql -v ON_ERROR_STOP=1 -d "$DB" -c "REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO compback_app; ALTER SCHEMA public OWNER TO compback_owner;"
