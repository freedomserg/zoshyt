#!/usr/bin/env bash
# Restore-drill (крок 8 плану, ADR-0006): нетестований бекап — не бекап.
#   Тягне ОСТАННІЙ дамп із бакета → розшифровує age-ключем → піднімає ТИМЧАСОВИЙ
#   postgres:17 (бойовий не чіпається) → pg_restore → контрольні запити
#   → прибирає за собою. Ганяти раз на місяць; дату фіксувати у плані.
# Це перевірка, що дамп читабельний, а НЕ процедура справжнього відновлення —
# та в ops/backup/README.md (ролі спершу створює init.sh, pg_restore без --no-*).
set -euo pipefail

REMOTE="b2:zoshyt-backups/pg"
AGE_KEY="/opt/zoshyt/backup/age.key"
CONTAINER="zoshyt-restore-drill"
TMP="$(mktemp -d)"
trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT

LATEST="$(rclone lsf "$REMOTE" --files-only | sort | tail -1)"
[ -n "$LATEST" ] || { echo "У бакеті порожньо — нема що перевіряти"; exit 1; }
echo "Останній дамп: $LATEST"

rclone copyto "$REMOTE/$LATEST" "$TMP/dump.age"
age -d -i "$AGE_KEY" -o "$TMP/dump" "$TMP/dump.age"

docker run -d --name "$CONTAINER" \
  -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=zoshyt postgres:17 >/dev/null
until docker exec "$CONTAINER" pg_isready -U postgres -q; do sleep 1; done

docker cp "$TMP/dump" "$CONTAINER:/tmp/dump" >/dev/null
# --no-owner: таблиці належать zoshyt_migrate, відновлюємо під postgres.
# --no-acl: у дампі GRANT для zoshyt_app/zoshyt_readonly і REVOKE на events
# (ADR-0015); ролі в дамп не потрапляють — без прапорця pg_restore падає.
docker exec "$CONTAINER" pg_restore -U postgres -d zoshyt --no-owner --no-acl /tmp/dump

echo "=== перевірка відновлених даних ==="
docker exec "$CONTAINER" psql -U postgres -d zoshyt -tAc \
  "select 'таблиць у public: '||count(*) from pg_tables where schemaname='public'"
docker exec "$CONTAINER" psql -U postgres -d zoshyt -tAc \
  "select 'events: '||count(*) from events"
docker exec "$CONTAINER" psql -U postgres -d zoshyt -tAc \
  "select 'остання подія: '||coalesce(max(recorded_at)::text, '(порожньо)') from events"
echo "RESTORE DRILL OK — $(date -u +%F)"
