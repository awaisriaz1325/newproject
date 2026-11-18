#!/usr/bin/env bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 -U postgres -c "CREATE DATABASE compback OWNER compback_owner"
psql -v ON_ERROR_STOP=1 -U postgres -d compback -c "REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE ON SCHEMA public TO compback_app; ALTER SCHEMA public OWNER TO compback_owner;"
