#!/bin/sh
set -eu

# POSTGRES_USER is the bootstrap administrator. The application connects with
# the separate POSTGRES_APP_USER role created and reconciled below.
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

url_decode() {
    encoded_value=$1
    printf '%s' "$encoded_value" | awk '
        function hex_value(character) {
            character = tolower(character)
            return index("0123456789abcdef", character) - 1
        }
        {
            decoded = ""
            for (position = 1; position <= length($0); position++) {
                character = substr($0, position, 1)
                if (character == "%" && position + 2 <= length($0)) {
                    high = hex_value(substr($0, position + 1, 1))
                    low = hex_value(substr($0, position + 2, 1))
                    if (high >= 0 && low >= 0) {
                        decoded = decoded sprintf("%c", high * 16 + low)
                        position += 2
                        continue
                    }
                }
                decoded = decoded character
            }
            printf "%s", decoded
        }
    '
}

if [ -n "${DATABASE_URL:-}" ]; then
    case "$DATABASE_URL" in
        postgresql://*|postgresql+asyncpg://*) ;;
        *)
            echo "DATABASE_URL must use a PostgreSQL scheme" >&2
            exit 1
            ;;
    esac

    connection_details=${DATABASE_URL#*://}
    encoded_credentials=${connection_details%@*}
    database_location=${connection_details##*@}

    if [ "$database_location" = "$connection_details" ] ||
       [ "${encoded_credentials#*:}" = "$encoded_credentials" ]; then
        echo "DATABASE_URL must contain a username, password, host, and database" >&2
        exit 1
    fi

    encoded_user=${encoded_credentials%%:*}
    encoded_password=${encoded_credentials#*:}
    location_without_query=${database_location%%\?*}
    encoded_database=${location_without_query#*/}

    if [ "$encoded_database" = "$location_without_query" ] ||
       [ -z "$encoded_database" ]; then
        echo "DATABASE_URL must name a database" >&2
        exit 1
    fi

    export INIT_DB_USER="$(url_decode "$encoded_user")"
    export INIT_DB_PASSWORD="$(url_decode "$encoded_password")"
    export INIT_DB_NAME="$(url_decode "$encoded_database")"
else
    export INIT_DB_USER="${POSTGRES_APP_USER:-app_user}"
    export INIT_DB_PASSWORD="${POSTGRES_APP_PASSWORD:-$POSTGRES_PASSWORD}"
    export INIT_DB_NAME="${POSTGRES_APP_DB:-$POSTGRES_DB}"
fi

export INIT_DB_SCHEMA="${POSTGRES_APP_SCHEMA:-auth}"
export PGPASSWORD="$POSTGRES_PASSWORD"

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<'SQL'
\getenv db_user INIT_DB_USER
\getenv db_password INIT_DB_PASSWORD
\getenv db_name INIT_DB_NAME

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'db_user', :'db_password')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name')
\gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', :'db_name', :'db_user')
\gexec
SQL

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$INIT_DB_NAME" <<'SQL'
\getenv db_user INIT_DB_USER
\getenv db_schema INIT_DB_SCHEMA

SELECT format(
    'CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION %I',
    :'db_schema',
    :'db_user'
)
\gexec

SELECT format('ALTER SCHEMA %I OWNER TO %I', :'db_schema', :'db_user')
\gexec
SQL
