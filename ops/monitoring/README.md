# Моніторинг — healthchecks.io (крок 9 плану)

Мінімум, як у lozar: dead-man's switch на кожну річ, що має відбуватися
регулярно, алерти в Telegram. Без Prometheus/Grafana/Sentry; логи —
`docker logs` / `journalctl`. Зовнішнього HTTP-монітора нема:
api-heartbeat з коду покриває «api живий» (крок 5), а падіння VPS
виявляє відсутність будь-яких пінгів.

Проєкт `zoshyt` у тому самому акаунті healthchecks, що й lozar; Telegram-
інтеграція проєкту → особистий чат [С] (той самий, що `ADMIN_CHAT_ID`).

## Чеки

| Чек | Schedule | Grace | Хто пінгує | Стан |
|---|---|---|---|---|
| `zoshyt-backup` | Cron `30 2 * * *`, tz UTC | 6 h | `/opt/zoshyt/backup/backup.sh` (URL у `/etc/cron.d/zoshyt-backup`) | активний з 2026-09-23 |
| `zoshyt-api-heartbeat` | Period 5 min | 10 min | api, кожні 5 хв → `HC_API_URL` | New до кроку 5 |
| `zoshyt-bot-heartbeat` | Period 5 min | 10 min | bot (APScheduler), кожні 5 хв → `HC_BOT_URL` | New до кроку 5 |
| `zoshyt-reminders` | Period 1 day | 3 h | джоба reminders о 09:00 Europe/Kyiv → `HC_REMINDERS_URL` | New до кроку 5 |

Новий чек до першого пінгу має статус New і не алертить — тому три
чеки заведені заздалегідь і мовчки чекають коду.

## Куди йдуть Ping URL

- `zoshyt-backup` — рядок `HC_BACKUP_URL=` у `/etc/cron.d/zoshyt-backup`
  (cron передає його в оточення `backup.sh`; порожньо = пінг пропускається).
- Три інші — у `/opt/zoshyt/.env` (`HC_API_URL`, `HC_BOT_URL`,
  `HC_REMINDERS_URL`, поля вже є в `config.py`), заповнюються на кроці 5
  разом з кодом, що пінгує. Пінг — `curl`/httpx GET на URL після
  успішного виконання; збій джоби = відсутність пінгу, не окремий
  сигнал.

Ping URL — секрет низької вартості (дозволяє лише пінгувати цей чек,
тобто маскувати збій). У чат/репо не вставляти; засвічений —
Regenerate у healthchecks і оновити місце, де він лежить.

## Перевірка алертів вживу (раз, після створення інтеграції)

```bash
curl -fsS '<Ping URL>/fail'   # → Telegram: «zoshyt-backup is DOWN»
curl -fsS '<Ping URL>'        # → «zoshyt-backup is UP»
```

Для чеків із коду (крок 5) ВИХІД плану: зупинити api на 15 хв →
алерт; запустити → resolved.

## Заповнити URL у cron (без секретів у чаті)

```bash
ssh zoshyt-prod
sudo sed -i 's|^HC_BACKUP_URL=.*$|HC_BACKUP_URL=<Ping URL>|' /etc/cron.d/zoshyt-backup
sudo grep -c "hc-ping.com" /etc/cron.d/zoshyt-backup   # 1
HC_BACKUP_URL='<Ping URL>' /opt/zoshyt/backup/backup.sh  # перший пінг — чек Up одразу
```

## Що дивитися, коли прийшов алерт

| Алерт | Перше, що зробити |
|---|---|
| `zoshyt-backup` DOWN | `ssh zoshyt-prod 'journalctl -t zoshyt-backup --no-pager \| tail -20'`; `rclone lsf b2:zoshyt-backups/pg`; `df -h /` |
| `zoshyt-api-heartbeat` DOWN | `curl -sS https://app.zoshyt.in.ua/health`; `docker compose -f /opt/zoshyt/docker-compose.prod.yml ps`; `… logs api --tail 100` |
| `zoshyt-bot-heartbeat` DOWN | `… logs bot --tail 100`; чи не запущений другий процес з тим самим токеном (getUpdates conflict) |
| `zoshyt-reminders` DOWN | `… logs bot` за 09:00 Europe/Kyiv; чи живий bot взагалі |
| усі чотири DOWN одночасно | VPS або мережа: Hetzner Console, `ssh zoshyt-prod uptime` |
