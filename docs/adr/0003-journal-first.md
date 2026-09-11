# ADR-0003 — Journal-first: append-only події + компенсація

Статус: accepted (2026-09)

## Контекст
Обіцянка продукту — дані не губляться (урок Всеосвіти). CRUD дозволяє
затерти чи втратити історію; потрібна повна відновлювана історія і
чесний експорт.

## Рішення
Подієвий облік — ядро (`journal/`):
- Таблиця `events` — append-only. Гарантія на рівні БД: app-юзер без
  прав UPDATE/DELETE на events (REVOKE), міграції — під окремим
  owner-юзером.
- Помилка виправляється компенсуючою подією, не редагуванням.
- Команда journal = запис події + оновлення проєкцій в ОДНІЙ
  транзакції.
- Проєкції (groups, balances, …) — похідні й перебудовувані з events;
  з'являються лише з екраном, який їх читає.
- api і bot ходять у journal через команди/запити — churn схеми подій
  лишається всередині journal.

## Альтернативи (відкинуті)
- Класичний CRUD — втрата історії, можливість затерти.
- Повноцінний ES/CQRS-фреймворк — оверкіл для масштабу.

## Наслідки
- Схема events: school_id (tenant+stream), seq, event_type,
  event_version, payload jsonb, actor_teacher_id, occurred_at,
  recorded_at, UNIQUE(school_id, seq).
- Факти — timestamptz UTC. Розклад занять — правило повторення
  (weekday + time, wall clock; tz — зі schools.tz), не момент часу.

## Для Claude Code
Ніколи UPDATE/DELETE по events — навіть у тестах і data-міграціях.
Компенсація — єдиний механізм виправлення. Нові типи подій —
з event_version=1 і фіксацією форми payload у docstring.
