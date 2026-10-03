"""Create only the configured project role/database; never alter existing ones.

Defaults to the configured server. Administrator credentials are prompted, not saved.
"""

import argparse
from getpass import getpass

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, help="Override the configured PostgreSQL port")
    args = parser.parse_args()
    url = make_url(get_settings().database_url.get_secret_value())
    if url.database != "job_application_os" or url.username != "job_application_os":
        raise SystemExit("This bootstrap only provisions the job_application_os database and role.")
    if not url.password:
        raise SystemExit("Configure the project role password in .env first.")
    connection_options = {
        "dbname": "postgres",
        "port": args.port or url.port or 5432,
        "autocommit": True,
        "connect_timeout": 5,
    }
    connection_options.update(
        host=url.host or "localhost",
        user="postgres",
        password=getpass("PostgreSQL administrator password: "),
    )
    with psycopg.connect(**connection_options) as connection:
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (url.username,)).fetchone():
            connection.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                    sql.Identifier(url.username), sql.Literal(url.password)
                )
            )
            print("Created project role.")
        else:
            print("Reusing project role without changing its password or privileges.")
        if not connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)).fetchone():
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(url.database),
                    sql.Identifier(url.username),
                )
            )
            print("Created project database.")
        else:
            print("Reusing project database without changing it.")


if __name__ == "__main__":
    main()
