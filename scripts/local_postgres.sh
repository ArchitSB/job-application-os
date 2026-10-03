#!/usr/bin/env bash
# Uses the installed PostgreSQL binaries; all data/logs/sockets stay in the project.
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pg_bin="${PG_BIN:-/usr/lib/postgresql/18/bin}"
pg_data="$project_root/.local/postgres/data"
pg_socket="$project_root/.local/postgres/socket"
pg_port="${PGPORT:-5433}"

case "${1:-status}" in
  init)
    mkdir -p "$pg_socket"
    chmod 700 "$project_root/.local/postgres"
    if [[ -f "$pg_data/PG_VERSION" ]]; then
      echo "Project cluster already initialized."
    else
      "$pg_bin/initdb" -D "$pg_data" --auth-local=peer --auth-host=scram-sha-256 --encoding=UTF8 --locale=C.UTF-8
    fi
    ;;
  start)
    if "$pg_bin/pg_ctl" -D "$pg_data" status >/dev/null 2>&1; then
      echo "Project cluster already running."
    else
      "$pg_bin/pg_ctl" -D "$pg_data" -l "$project_root/.local/postgres/server.log" \
        -o "-h localhost -p $pg_port -k '$pg_socket'" start
    fi
    ;;
  stop) "$pg_bin/pg_ctl" -D "$pg_data" -m fast stop ;;
  status) "$pg_bin/pg_ctl" -D "$pg_data" status ;;
  *) echo "Usage: bash scripts/local_postgres.sh {init|start|stop|status}" >&2; exit 2 ;;
esac
