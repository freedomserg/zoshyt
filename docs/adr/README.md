# ADR — індекс

Architecture Decision Records: короткі документи «чому саме так і що
відкинуто». Формат: NNNN-kebab.md, ≤1 сторінка, секції Статус /
Контекст / Рішення / Альтернативи / Наслідки / «Для Claude Code».

## Протокол
1. Рішення обговорюється і закривається в чаті ([С] + Claude).
2. Чат видає текст ADR → коміт у docs/adr/.
3. Задача в Claude Code: «реалізуй X за ADR-NNNN».
4. Реалізація суперечить ADR → питання повертається в чат, не
   обходиться в коді.
5. Зміна рішення → НОВИЙ ADR зі полем Supersedes; старі ADR не
   редагуються заднім числом.

## Індекс
| № | Назва | Суть |
|---|---|---|
| [0001](0001-mini-app-first.md) | Mini App first | Ф1 — лише Telegram Mini App; PWA відкладено, але дешево досяжно (auth-адаптер, teacher_id, dev-режим) |
| [0002](0002-fastapi-sqlalchemy-stack.md) | Бекенд-стек | FastAPI + SQLAlchemy 2 async (asyncpg) + Alembic; Postgres 17; async усюди |
| [0003](0003-journal-first.md) | Journal-first | append-only події, компенсація, подія+проєкція в одній транзакції |
| [0004](0004-long-polling.md) | Long polling | без webhook попри наявний 443 |
| [0005](0005-single-vps-compose.md) | Один VPS + compose | без k8s і managed free tier; Caddy для TLS |
| [0006](0006-backups.md) | Бекапи | pg_dump → age (client-side) → B2; tested restore; не R2 |
| [0007](0007-data-portability.md) | Data portability | повний експорт власнику — вимога рівня MVP |
| [0008](0008-no-payments.md) | Без еквайрингу | оплати — ручна фіксація подіями |
| [0009](0009-pii-minimization.md) | Мінімізація PII | лише ім'я дитини + контакт батька |
| [0010](0010-repo-layout.md) | Розкладка репо | monorepo, один пакет, два процеси; граф імпортів; інструменти |
| [0011](0011-export-channel.md) | Канал експорту | пул (кнопка CSV) обов'язково; пуш у TG; email — за тригером |
