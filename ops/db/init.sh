#!/bin/bash
# Ролі БД (крок 4 плану, ADR-0003). Образ postgres виконує цей скрипт ОДИН раз —
# при першому старті ПОРОЖНЬОГО volume. Локально після змін: docker compose down -v.
# У CI той самий скрипт запускається через docker exec у service container.
#   zoshyt_migrate — owner баз; під ним ходить alembic (сервіс migrate)
#   zoshyt_app     — під ним api і bot; UPDATE/DELETE на events знімає ревізія init
# Паролі — з env (POSTGRES_PASSWORD), у SQL не хардкодяться.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
	CREATE ROLE zoshyt_migrate LOGIN PASSWORD '$POSTGRES_PASSWORD';
	CREATE ROLE zoshyt_app     LOGIN PASSWORD '$POSTGRES_PASSWORD';
	ALTER DATABASE "$POSTGRES_DB" OWNER TO zoshyt_migrate;
	CREATE DATABASE zoshyt_test OWNER zoshyt_migrate;
SQL

# Default privileges діють у межах однієї бази — тому на кожну окремо.
# Майбутні таблиці/sequence, створені міграціями під zoshyt_migrate,
# отримують права для app автоматично, без GRANT у кожній ревізії.
# USAGE на sequences — інакше INSERT у таблицю з bigserial під app впаде.
for db in "$POSTGRES_DB" zoshyt_test; do
	psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<-SQL
		ALTER DEFAULT PRIVILEGES FOR ROLE zoshyt_migrate
			GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zoshyt_app;
		ALTER DEFAULT PRIVILEGES FOR ROLE zoshyt_migrate
			GRANT USAGE, SELECT ON SEQUENCES TO zoshyt_app;
	SQL
done
