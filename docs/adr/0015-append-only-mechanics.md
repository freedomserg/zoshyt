# ADR-0015 — Механіка append-only журналу: ролі БД, seq, межі винятків

Статус: accepted (2026-09-20)

## Контекст
ADR-0003 фіксує принцип (append-only події, компенсація, подія +
проєкції в одній транзакції), але МЕХАНІКА — як саме БД це гарантує —
була розкидана між планом, init.sh, ревізією 20260919_1_init і
коментарями в моделях. Перед першою командою journal (крок 5) [К] і
Claude Code мають читати одне місце, не археологію. Тут консолідація
ухваленого і одне нове рішення (третя роль); решта — без змін.

## Рішення

### Три ролі БД (init.sh, при першому старті порожнього volume)
- `zoshyt_migrate` — owner БД; під ним ходить лише alembic
  (one-shot сервіс migrate; env DB_MIGRATE_URL).
- `zoshyt_app` — під ним api і bot (env DB_URL).
- `zoshyt_readonly` — SELECT-only; для людини (ssh-тунель з ADR-0014,
  DBeaver): «дивитися очима» фізично не може писати. НОВЕ рішення;
  застосовується і в lozar (паритет).
- Default privileges від zoshyt_migrate: app — SELECT, INSERT,
  UPDATE, DELETE + USAGE/SELECT на sequences; readonly — SELECT.
  Майбутні проєкції отримують права автоматично, без GRANT у кожній
  ревізії.
- Один POSTGRES_PASSWORD на суперюзера й ролі: ролі розділяють
  привілеї, не довіру — всі секрети в одному .env (chmod 600).

### events — задокументований виняток
- У ревізії, що створює events: REVOKE UPDATE, DELETE ON events FROM
  zoshyt_app (default privileges вже видали — тому саме revoke).
- Отже: події не редагуються і не видаляються НІКИМ, крім
  migrate-ролі; помилка виправляється компенсуючою подією (ADR-0003).
- FK: school_id NOT NULL → schools, actor_teacher_id NULL → teachers,
  без ON DELETE-каскадів. Подія-привид для неіснуючої школи —
  гарантовано баг (обхід journal); його ловить БД, не ревʼю.

### Порядок журналу: seq, не id
- `events.id bigserial` — НЕ порядок: він глобальний на всі школи і з
  дірками (sequence не відкочується транзакцією).
- Порядок tenant-а — `seq`, щільний у межах school_id. Ним сортуються
  перебудова проєкцій і експорт CSV (ADR-0011).
- seq видає journal, не БД: перша дія команди в транзакції —
  `UPDATE schools SET last_seq = last_seq + 1 WHERE id = :school_id
  RETURNING last_seq`. Row lock на рядку школи серіалізує паралельні
  команди одного tenant-а (1–5 викладачів — достатньо назавжди в
  масштабі MVP); retry-логіка не потрібна.
- UNIQUE (school_id, seq) — страхувальна сітка і єдиний додатковий
  індекс V1.

### Межі винятків
- TRUNCATE бази zoshyt_test між тестами під migrate-роллю — скидання
  світу, не корекція даних; дозволено (лише zoshyt_test). zoshyt_app
  привілею TRUNCATE не має — межу тримає БД.
- Data-міграції під migrate-роллю технічно можуть усе; політика —
  НІКОЛИ не переписувати payload/семантику подій. Виправлення даних —
  компенсацією; міграція торкається events лише структурно (нова
  колонка, індекс).

## Альтернативи (відкинуті)
- seq через max(seq)+1 з retry на IntegrityError — більше коду і
  концепцій без виграшу на нашій конкуренції.
- Тригер заборони UPDATE/DELETE замість REVOKE — складніше за права,
  однакова гарантія.
- Дві ролі без readonly — людина під тунелем мала б INSERT у журнал.
- Окремі паролі на ролі — театр безпеки в межах одного .env.

## Наслідки
- init.sh: +роль zoshyt_readonly, +default privileges SELECT для неї.
  Локально init.sh виконується лише на свіжому volume →
  `docker compose down -v` один раз.
- ADR-0014 читається з уточненням: під ssh-тунелем — роль
  zoshyt_readonly (не zoshyt_app).
- Runbook ops/vps: рядок підключення DBeaver — readonly-роль.

## Для Claude Code
Кожна команда journal: (1) відкрити транзакцію; (2) видати seq через
UPDATE schools … RETURNING; (3) INSERT у events; (4) оновити проєкції;
(5) commit — усе в ОДНІЙ транзакції. Читання — окремо, без seq.
Ніколи не використовувати events.id як порядок. Нові ролі/гранти —
лише через ADR.
