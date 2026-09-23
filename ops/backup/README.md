# Backup runbook — zoshyt-prod (крок 8 плану)

Щоденний зашифрований дамп Postgres у Backblaze B2 і щомісячний
restore-drill. Дзеркало lozar (2026-09-06); відмінності zoshyt позначені
**[≠ lozar]**. Після кожного блоку — перевірка. Секретів у файлі нема.

Рішення: ADR-0006 (pg_dump → age → B2, retention 30д, tested restore),
ADR-0015 (три ролі БД — звідси прапорці pg_restore), ADR-0009 (PII у
журналі — тому шифрування client-side обов'язкове; SSE-B2 його не
замінює).

Що де живе:

| Де | Що |
|---|---|
| репо `ops/backup/` | `backup.sh`, `restore-drill.sh`, цей README |
| VPS `/opt/zoshyt/backup/` | ті самі скрипти (кладе deploy-job, **[≠ lozar]**) + `age.key` (600, руками) |
| VPS `~deploy/.config/rclone/rclone.conf` | ремоут `[b2]` з keyID/applicationKey (600, руками) |
| VPS `/etc/cron.d/zoshyt-backup` | розклад 02:30 UTC + `HC_BACKUP_URL` |
| B2 бакет `zoshyt-backups`, тека `pg/` | `zoshyt-<UTC>.dump.age`, ≤30 днів |
| менеджери паролів [С] і [К] | приватний age-ключ, keyID/applicationKey |

## 0. B2 Console: application key

Бакет `zoshyt-backups` уже є (Private, Object Lock вимкнено — конфліктує
з retention; Default Encryption байдуже, age шифрує до відправки).
App Keys → Add a New Application Key:

- Name `zoshyt-vps`; **Allow access to Bucket(s): лише `zoshyt-backups`**
  (компрометація ключа з VPS ≠ доступ до інших бакетів);
- Type of Access **Read and Write** (бекап пише, drill читає, retention
  видаляє); prefix і duration порожні (це cron, не людина).

`keyID` і `applicationKey` показуються один раз → одразу в менеджер
паролів.

## 1. На VPS: age і rclone

```bash
sudo apt install -y age
curl -fsSL https://rclone.org/install.sh | sudo bash
age --version && rclone version | head -1
```

age — з apt Ubuntu 24.04 (1.1.x); rclone — офіційний інсталятор, як на
lozar-prod (у apt застаріла версія без свіжого B2-бекенда).

## 2. rclone: ремоут `[b2]`

Значення вставляє [С] прямо в термінал на VPS — секрети не проходять
через чат.

```bash
umask 077 && mkdir -p ~/.config/rclone
cat > ~/.config/rclone/rclone.conf <<'CONF'
[b2]
type = b2
account = <keyID>
key = <applicationKey>
CONF
```

Connectivity-тест (пише, читає, видаляє тестовий файл):

```bash
echo ping | rclone rcat b2:zoshyt-backups/connectivity-test.txt
rclone cat b2:zoshyt-backups/connectivity-test.txt
rclone deletefile b2:zoshyt-backups/connectivity-test.txt
```

## 3. age-ключ

```bash
mkdir -p /opt/zoshyt/backup
age-keygen -o /opt/zoshyt/backup/age.key
chmod 600 /opt/zoshyt/backup/age.key
age-keygen -y /opt/zoshyt/backup/age.key     # публічний ключ (age1…) — у backup.sh
```

- Публічний ключ (`age1…`) вписується в `AGE_RECIPIENT` у
  `ops/backup/backup.sh` і комітиться — він не секрет.
- Приватний (`AGE-SECRET-KEY-1…`, вміст `age.key`) — у менеджери паролів
  **обох** ([С] і [К]). Без нього дампи — шум; VPS може зникнути разом
  із ключем. DoD плану: «age-ключ у двох місцях».

## 4. Скрипти на VPS і перший бекап

До merge PR скрипти кладуться руками тією самою командою, що потім
виконує deploy-job:

```bash
scp -p ops/backup/backup.sh ops/backup/restore-drill.sh zoshyt-prod:/opt/zoshyt/backup/
ssh zoshyt-prod '/opt/zoshyt/backup/backup.sh'
ssh zoshyt-prod 'rclone lsf b2:zoshyt-backups/pg'
```

Очікую `backup ok: zoshyt-<stamp>.dump.age (…K)` і той самий файл у
списку. Негативна перевірка, що файл справді зашифрований:

```bash
ssh zoshyt-prod 'rclone cat "b2:zoshyt-backups/pg/$(rclone lsf b2:zoshyt-backups/pg | tail -1)" | head -c 40; echo'
```

має показати `age-encryption.org/v1`, а не бінарний заголовок `PGDMP`.

## 5. cron

```bash
sudo tee /etc/cron.d/zoshyt-backup > /dev/null <<'CRON'
# Щоденний бекап zoshyt (крок 8). HC_BACKUP_URL заповниться на кроці 9.
HC_BACKUP_URL=
30 2 * * * deploy /opt/zoshyt/backup/backup.sh 2>&1 | logger -t zoshyt-backup
CRON
sudo cat /etc/cron.d/zoshyt-backup
```

Вивід іде в journal: `journalctl -t zoshyt-backup`. Перевірка
наступного ранку — новий файл у бакеті за сьогоднішньою датою.

## 6. Restore-drill (раз на місяць, руками)

```bash
ssh zoshyt-prod '/opt/zoshyt/backup/restore-drill.sh'
```

Очікую: `Останній дамп: …`, `таблиць у public: 5` (schools, teachers,
school_members, events, alembic_version), `events: N`, `остання подія: …`,
`RESTORE DRILL OK — <дата>`. Тимчасовий контейнер прибирається сам
(`docker ps -a | grep drill` — порожньо). Дату записати в план; наступний
— через місяць.

Drill відновлює з `--no-owner --no-acl`: у дампі власник `zoshyt_migrate`
і GRANT/REVOKE для `zoshyt_app`/`zoshyt_readonly`, а ролі в дамп не
потрапляють. Це перевірка читабельності дампа, не справжнє відновлення.

## 7. Справжнє відновлення на новому сервері (не drill)

Порядок важливий: ролі мають існувати ДО pg_restore, і тоді власник і
права відновлюються як були.

1. Кроки 1–9 runbook `ops/vps/README.md` (сервер, Docker, `/opt/zoshyt`,
   `.env`; `POSTGRES_PASSWORD` може бути новим — ролі створюються
   заново); `age.key` з менеджера паролів → `/opt/zoshyt/backup/age.key`
   (600); rclone.conf як у блоці 2.
2. Лише Postgres, на порожньому volume — `init.sh` створить три ролі:
   ```bash
   cd /opt/zoshyt && docker compose -f docker-compose.prod.yml up -d postgres
   ```
3. Останній дамп → розшифрувати → відновити з правами:
   ```bash
   LATEST=$(rclone lsf b2:zoshyt-backups/pg --files-only | sort | tail -1)
   rclone copyto "b2:zoshyt-backups/pg/$LATEST" /tmp/dump.age
   age -d -i /opt/zoshyt/backup/age.key -o /tmp/dump /tmp/dump.age
   docker compose -f docker-compose.prod.yml cp /tmp/dump postgres:/tmp/dump
   docker compose -f docker-compose.prod.yml exec -T postgres pg_restore -U postgres -d zoshyt /tmp/dump
   rm -f /tmp/dump /tmp/dump.age
   ```
4. `alembic_version` уже в дампі → `migrate` побачить head і нічого не
   зробить; далі звичайний деплой: `IMAGE_TAG=<sha12> docker compose -f
   docker-compose.prod.yml up -d`.
5. Перевірка: `/health`, `select count(*) from events` під
   `zoshyt_readonly`, `delete from events` під `zoshyt_app` → permission
   denied (права відновилися).
