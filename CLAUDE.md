# CLAUDE.md

Zoshyt — облік для репетиторів і міні-шкіл: Telegram Mini App + бот.
Стек: Python 3.12 (uv), FastAPI + SQLAlchemy 2 async (asyncpg) +
Alembic, aiogram 3 (long polling), APScheduler у процесі бота,
Postgres 17, React + Vite + TS (miniapp/), Docker Compose, Caddy у
проді. Рішення і причини — docs/adr/README.md; суперечність коду з
ADR повертається в обговорення, а не обходиться в коді.

## Команди
- `make up` — Postgres у контейнері
- `make check` — ruff + mypy + import-linter + pytest (те саме жене CI)
- `make dev` — api (uvicorn --reload) + bot + vite разом
- `uv run alembic revision -m "slug"` / `uv run alembic upgrade head`
- `pnpm -C miniapp build`
- Реліз-тег: `git tag vX.Y.Z && git push --tags` на коміті з main, ПІСЛЯ
  зеленого Release (ADR-0013; ранній тег гучно падає — це запобіжник,
  Re-run після Release). Відкат на VPS — `IMAGE_TAG=<X.Y.Z або sha12>
  docker compose -f docker-compose.prod.yml up -d`

## Межі (enforcement: import-linter, не «на совість»)
- journal ← api, bot, notify; auth ← api, bot; db ← journal, api, bot
- api ↛ bot, bot ↛ api — спільне лише через journal
- journal НЕ імпортує fastapi/aiogram
- Про initData знає лише auth/ (бекенд) і api/auth.ts (фронт).
  Авторизація — тільки через адаптер; назовні — TeacherId
- Повідомлення батькам — тільки через notify/

## Правила даних
- events — append-only: НІКОЛИ UPDATE/DELETE (навіть у тестах і
  data-міграціях). Помилка = компенсуюча подія
  (виняток: TRUNCATE тестової БД zoshyt_test між тестами під
  migrate-роллю — це скидання світу, не корекція даних)
- Команда journal = подія + оновлення проєкцій в ОДНІЙ транзакції
  (правило текстом: до першого екрана референсної реалізації нема)
- Проєкції — похідні від events, перебудовувані; нова read-модель —
  лише з екраном, який її читає
- Міграції — лише alembic; --autogenerate — чернетка, кожну ревізію
  читати очима; ім'я ревізії YYYYMMDD_n_slug, не хеш
- Час: у БД timestamptz UTC; показ — за schools.tz (Europe/Kyiv).
  Розклад занять — wall clock (weekday + time, tz зі schools.tz),
  НЕ timestamptz; конвертація wall→UTC — через zoneinfo у момент
  обчислення конкретної дати
- PII — лише ім'я дитини + контакт батька. Нове PII-поле — тільки
  через ADR. payload подій не логувати в prod; фікстури — вигадані дані
- Суми — integer у копійках; валюта — поле події ('UAH')

## Обмеження продукту
- 5 екранів: групи/учні, розклад, відмітка присутності, оплати
  (ручна фіксація, БЕЗ еквайрингу), боржники+нагадування
- Ролі — лише owner/teacher. Тенант — school_id у КОЖНОМУ запиті journal
- Нова фіча — лише після запиту реального користувача
- Експорт CSV з events власнику — вимога рівня MVP (ADR-0007/0011)

## Підводні камені
- initData живе ~24 год — не кешувати назавжди; 401 від api =
  «перевідкрий Mini App», не цикл ретраїв
- AUTH_MODE=dev у prod → процес МУСИТЬ впасти на старті
- iOS webview: не покладатися на 100vh; safe-area; BackButton
- callback_data ≤ 64 байти
- getUpdates — один процес на токен (звідси окремі dev-боти)
- Два процеси (api, bot) з одного образу — міграції ТІЛЬКИ через
  one-shot сервіс migrate, не на старті процесів
- Необроблені винятки обох процесів → лог + повідомлення в
  ADMIN_CHAT_ID
- prod-compose: `ports:` лише у caddy (80/443) і postgres на
  `127.0.0.1:5432` (ADR-0014). Docker відкриває порти повз ufw —
  без префікса `127.0.0.1:` база опиниться в інтернеті. Людина під
  ssh-тунелем ходить роллю zoshyt_readonly (SELECT-only, ADR-0015);
  нові ролі/гранти — лише через ADR
