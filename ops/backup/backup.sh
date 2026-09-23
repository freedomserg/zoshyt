#!/usr/bin/env bash
# Щоденний бекап prod-Postgres (крок 8 плану, ADR-0006):
#   pg_dump -Fc → age (шифрування публічним ключем) → rclone у B2 → retention 30д
#   → пінг healthchecks (HC_BACKUP_URL задається в cron; порожньо = пропустити).
# Запускається cron'ом від deploy на VPS. Живе в репо: ops/backup/backup.sh;
# на сервер кладе deploy-job (release.yml) у /opt/zoshyt/backup/.
# Дзеркало lozar ops/backup/backup.sh; відмінності — ремоут, база, суперюзер.
set -euo pipefail

REMOTE="b2:zoshyt-backups/pg"
AGE_RECIPIENT="age17g8f69glvp96kghelxn28lgnwrsa3ytjxzmnn2eun3503qskrqxq7s2afd"
KEEP="30d"
HC_BACKUP_URL="${HC_BACKUP_URL:-}"
COMPOSE="docker compose -f /opt/zoshyt/docker-compose.prod.yml"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
NAME="zoshyt-$STAMP.dump.age"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# pg_dump усередині контейнера під суперюзером postgres: локальний сокет,
# пароль не потрібен. У дампі — власник zoshyt_migrate і права app/readonly
# (ролі в дамп не потрапляють — див. restore-drill.sh і README).
$COMPOSE exec -T postgres pg_dump -U postgres -Fc zoshyt > "$TMP/dump"
age -r "$AGE_RECIPIENT" -o "$TMP/$NAME" "$TMP/dump"
rclone copyto "$TMP/$NAME" "$REMOTE/$NAME"

# Retention: прибрати дампи, старші за 30 днів.
rclone delete --min-age "$KEEP" "$REMOTE"

if [ -n "$HC_BACKUP_URL" ]; then
  curl -fsS -m 10 --retry 3 "$HC_BACKUP_URL" >/dev/null
fi

echo "backup ok: $NAME ($(du -h "$TMP/$NAME" | cut -f1))"
