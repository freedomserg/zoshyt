# Zoshyt

Простий і надійний облік для репетиторів, гуртків і міні-шкіл: групи,
відвідування, оплати, нагадування батькам. Telegram Mini App + бот.
Базовий функціонал безкоштовний; головна обіцянка продукту — **дані не
губляться і завжди можуть бути вивантажені назовні**.

Цей README — єдине джерело правди для налаштування робочого місця і
щоденної роботи. Правило: **кожне питання, на яке README не відповів, —
це правка README** (окремим PR), а не усна відповідь.

---

## 1. Як влаштована система

Три процеси і одна база:

```
   Telegram-клієнт (телефон / десктоп)
     │                     │
  чат з ботом         webview «Mini App»
     │                     │  ← тут виконується React-UI
     │                     │
     │            HTTPS: сторінка + /api/*
     │                     ▼
     │           [api] FastAPI (:8000)
     │                     │
 long polling              │ команди / запити
     ▼                     ▼
 [bot] aiogram ──────► [journal] ядро домену
                           │
                           ▼
                       PostgreSQL
```

- **bot** — процес, що сам ходить до Telegram по long polling
  (`getUpdates`). Публічної адреси не має і не потребує. Реагує на
  `/start`, надсилає нагадування батькам, ставить у повідомлення кнопку,
  що відкриває Mini App.
- **Mini App** — наш React-застосунок, який Telegram відкриває у
  вбудованому браузері (webview). Код віддається з Vite (локально) або
  з api (у проді). Всі дані отримує запитами до api.
- **api** — FastAPI-процес: перевіряє авторизацію, викликає journal,
  повертає JSON.
- **journal** — доменне ядро (див. нижче). Єдине місце, де живе
  бізнес-логіка. І bot, і api — лише тонкі «перекладачі» до нього.

### Подієва модель (event sourcing) — у трьох поняттях

- **Подія** — незмінний факт: `TeacherRegistered`, `PaymentRecorded`.
  Зберігається в таблиці `events` назавжди. Оновлювати чи видаляти
  події не можна — на рівні прав БД. Помилка виправляється
  **компенсуючою подією** («оплату скасовано»), як сторно в
  бухгалтерії.
- **Команда** — намір щось змінити: `RegisterTeacher`. Функція в
  journal, яка валідує вхід, записує подію та оновлює проєкції —
  **в одній транзакції**.
- **Проєкція (read-модель)** — зручна для читання таблиця (`groups`,
  `balances`), похідна від подій. Її можна знищити й перебудувати з
  events; істина — завжди в журналі подій.

Навіщо так: append-only журнал фізично не дає «затерти» дані, а експорт
сирих подій — це повна історія школи. Це і є технічне втілення обіцянки
надійності.

---

## 2. Структура репозиторію

```
zoshyt/
  pyproject.toml        маніфест Python-пакета: залежності + конфіги інструментів
  uv.lock               точні версії всіх залежностей (генерує uv, комітиться)
  .python-version       версія Python для uv (3.12)
  Makefile              словник команд проєкту: up / check / dev
  Dockerfile            один multi-stage образ: збірка фронта + Python-пакет
  docker-compose.yml    dev-інфраструктура (Postgres у контейнері)
  docker-compose.prod.yml  prod-розкладка (caddy + migrate + api + bot + postgres)
  .env.example          перелік env-змінних без значень; копіюється в .env
  CLAUDE.md             контекст для Claude Code: межі, правила даних, команди
  docs/adr/             Architecture Decision Records — «чому саме так»
  design/handoff/       бандли екранів від Claude Design (джерело правди для UI)
  .github/workflows/    CI (перевірки на PR) і CD (деплой з main)

  src/zoshyt/
    journal/            ЯДРО: події, команди, запити, EventStore.
                        Не знає нічого про Telegram і HTTP.
    auth/               адаптер автентифікації: перевірка підпису initData
                        (Telegram), DevAuth для локальної розробки. Віддає
                        TeacherId; «хто підписав» — деталь адаптера.
    api/                FastAPI: роутери екранів, /health, віддача статики
                        Mini App у проді. Тонкий шар над journal.
    bot/                aiogram: /start, кнопка web_app, нагадування,
                        APScheduler-джоби. Тонкий шар над journal.
    db/                 engine, сесії, SQLAlchemy-моделі, alembic-міграції.
                        «Як зберігається»; сенс даних — у journal.
    notify/             інтерфейс Notifier (send_to_parent) + Telegram-
                        реалізація. Точка майбутнього розширення (Viber/SMS).
    config.py           налаштування з env через pydantic-settings.

  miniapp/              React + Vite + TypeScript (SPA, 5 екранів)
    src/api/client.ts   ЄДИНЕ місце HTTP-викликів (додає auth-заголовок)
    src/api/auth.ts     auth-клієнт: initData у Telegram / dev-заголовок у браузері
    src/screens/        по файлу на екран
    src/theme.ts        themeParams Telegram → CSS-змінні
```

### Конституція (перевіряється CI, не «на совість»)

Граф імпортів — хто кого може імпортувати:

```
journal ← api, bot, notify      journal не знає нікого
auth    ← api, bot
db      ← journal, api, bot
api ↛ bot,  bot ↛ api           спільне — ЛИШЕ через journal
```

Порушення (наприклад, `import fastapi` всередині journal) завалить
`make check` — це робить import-linter.

Правила даних:

- `events` — append-only: ніколи UPDATE/DELETE; помилка = компенсуюча
  подія. Гарантується правами БД (app-юзер не має UPDATE/DELETE).
- Команда journal = подія + оновлення проєкції **в одній транзакції**.
- Міграції — тільки через alembic, кожну ревізію читати очима.
- Час: у БД — UTC (timestamptz); показ — за timezone школи
  (Europe/Kyiv за замовчуванням). Розклад занять — «час стіни»
  (weekday + time), не момент часу.
- PII мінімізовано: лише ім'я дитини та контакт батька. Ні адрес, ні
  дат народження.
- `initData` живе ~24 години — не кешувати назавжди; 401 = перевідкрити
  Mini App.
- `AUTH_MODE=dev` дозволений тільки локально; у проді процес мусить
  впасти на старті, якщо він увімкнений.

Продуктові межі: 5 екранів, без прийому платежів, ролі — лише
власник/викладач. Нова фіча — тільки після запиту реального користувача.

---

## 3. Що поставити на комп'ютер (macOS)

Порядок має значення. Після кожного блоку — команда перевірки.

### 3.1 Homebrew — менеджер програм для macOS

Через нього ставиться все інше.

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew --version
```

### 3.2 Git + доступ до GitHub

Git на macOS зазвичай уже є (`git --version`; якщо спитає про Xcode
Command Line Tools — погодитися). Далі:

```bash
git config --global user.name  "Kateryna ..."
git config --global user.email "твій-email-на-GitHub"

# SSH-ключ для GitHub:
ssh-keygen -t ed25519 -C "kateryna@zoshyt"     # Enter, Enter, парольна фраза
pbcopy < ~/.ssh/id_ed25519.pub                  # публічний ключ у буфер
```

GitHub → Settings → SSH and GPG keys → New SSH key → вставити.
Прийняти запрошення-collaborator у репо `zoshyt` (прийде на пошту).

```bash
git clone git@github.com:<акаунт-Сергія>/zoshyt.git && cd zoshyt
```

### 3.3 uv — усе для Python однією програмою

uv сам ставить потрібну версію Python, створює віртуальне середовище,
ставить залежності за `uv.lock` і запускає команди. Нічого з
екосистеми «poetry / pyenv / pip» окремо вчити не треба.

```bash
brew install uv
uv python install 3.12
uv run --python 3.12 python --version   # → Python 3.12.x
```

Системний Python (у macOS це старий 3.9) не чіпаємо ніколи.

### 3.4 Node 22 + corepack + pnpm — для фронтенду

Node — середовище виконання JS-інструментів; pnpm — менеджер
JS-пакетів; corepack (вбудований у Node) сам підставляє правильну
версію pnpm, записану в репо.

```bash
brew install node@22
brew link --overwrite node@22     # якщо brew попросить — додати шлях у ~/.zshrc, він покаже рядок
node --version                    # → v22.x
corepack enable
pnpm --version                    # на перший раз спитає дозвіл завантажити — Y
```

### 3.5 Docker Desktop — контейнери

Postgres локально живе ТІЛЬКИ в контейнері — на комп'ютер він не
ставиться.

```bash
brew install --cask docker
open -a Docker                    # дочекатися «running» у менюбарі
docker --version
docker compose version            # має бути v2+ (команда через пробіл)
docker run --rm hello-world
```

### 3.6 VS Code + розширення

```bash
brew install --cask visual-studio-code
```

Розширення (⇧⌘X): **Python**, **Pylance**, **ESLint**. Спільні
налаштування (формат при збереженні через ruff тощо) вже в репо у
`.vscode/settings.json` — нічого налаштовувати руками.
(PyCharm Community — допустима альтернатива, якщо звичніше; але не
обидва одразу.)

### 3.7 DBeaver — дивитися базу очима

```bash
brew install --cask dbeaver-community
```

Підключення до локального Postgres (після першого `make up`):
host `localhost`, port `5432`, database/user/password — з твого `.env`.
Корисно відкривати таблицю `events` і дивитися jsonb-payload подій.

### 3.8 cloudflared — тунель для справжнього Telegram

Навіщо: Mini App усередині Telegram відкривається лише по публічному
HTTPS. Тунель робить твій локальний Vite (`localhost:5173`) доступним
за стабільною адресою `https://dev-k.zoshyt.in.ua` — без відкритих
портів на ноуті.

Тунель `zoshyt-dev-k` і DNS-запис уже створені (вони прив'язані до
Cloudflare-акаунта проєкту). Як це влаштовано, щоб не плутатися:

- Тунелів **два** — `zoshyt-dev-s` (Сергій) і `zoshyt-dev-k` (твій).
  У кожного свій UUID і свій credentials-файл `<UUID>.json` — це
  секрет конкретного тунелю. Файли НЕ взаємозамінні: json від dev-s
  не запустить dev-k, і навпаки.
- Створення тунелів і DNS-записів (`tunnel create`, `tunnel route
  dns`) — разові адмін-операції; їх робить Сергій зі своєї машини,
  бо потребують `cert.pem` — ключа керування зоною. Тобі ці команди
  не потрібні ніколи: для запуску тунелю достатньо credentials-файла.
- Якщо credentials-файл скомпрометовано — тунель видаляється
  (`tunnel delete`) і створюється заново; твій файл при цьому ніяк
  не залежить від файла dev-s.

Хто що тримає:

| Де | Що лежить |
|---|---|
| Машина Сергія | `cert.pem` (адмін-право на тунелі), `<UUID-s>.json`, config для dev-s |
| Спільне сховище | `zoshyt-dev-k.json` + UUID тунелю dev-k (транзит для тебе) |
| Твоя машина | лише `zoshyt-dev-k.json` + свій config.yml |

**Передумова на машині Сергія** (разово, ДО кроків нижче; якщо
`cloudflared tunnel list` вже показує `zoshyt-dev-k` — усе зроблено):

```bash
# 1) створити тунель — у виводі буде UUID, на диску з'явиться
#    ~/.cloudflared/<UUID-k>.json:
cloudflared tunnel create zoshyt-dev-k

# 2) прив'язати DNS-ім'я (створить CNAME dev-k → <UUID-k>.cfargotunnel.com):
cloudflared tunnel route dns zoshyt-dev-k dev-k.zoshyt.in.ua

# 3) контроль — два тунелі, dev-s і dev-k:
cloudflared tunnel list

# 4) передати credentials у спільне сховище під ім'ям zoshyt-dev-k.json
#    (разом із самим UUID), тимчасову копію прибрати:
cp ~/.cloudflared/<UUID-k>.json ~/Desktop/zoshyt-dev-k.json
#    → завантажити з Desktop у сховище → rm ~/Desktop/zoshyt-dev-k.json
```

Тобі потрібно лише:

```bash
brew install cloudflared
mkdir -p ~/.cloudflared
```

1. Візьми зі спільного сховища паролів файл **`zoshyt-dev-k.json`**
   (credentials тунелю) і поклади його в `~/.cloudflared/`.
2. Створи файл `~/.cloudflared/config.yml`:

```yaml
tunnel: <UUID-тунелю-dev-k>        # він же — ім'я json-файла; є у сховищі
credentials-file: /Users/<твій-юзер>/.cloudflared/zoshyt-dev-k.json
ingress:
  - hostname: dev-k.zoshyt.in.ua
    service: http://localhost:5173
  - service: http_status:404
```

3. Запуск (окремий термінал, працює поки відкритий):

```bash
cloudflared tunnel run
```

Перевірка без проєкту: у другому терміналі
`python3 -m http.server 5173`, потім відкрий
`https://dev-k.zoshyt.in.ua` у браузері — побачиш лістинг файлів по
HTTPS. Коди помилок, якщо щось не так: **530** — тунель не запущений;
**502** — тунель працює, але на 5173 ніхто не слухає.

### 3.9 Менеджер паролів

У спільному сховищі лежать: токен бота `@zoshyt_dev_k_bot` (це і твій
секрет для `.env`), credentials тунелю, згодом — age-ключ бекапів.
Токени ніколи не вставляються в чат/код/скріншоти; засвічений токен
одразу перевипускається.

---

## 4. Локальний запуск

```bash
cp .env.example .env    # один раз; заповнити значення (нижче)
make up                 # підняти Postgres у контейнері
make check              # усі перевірки: має бути зелено
make dev                # api + bot + vite разом
```

Мінімум для `.env` на твоїй машині:

```
APP_ENV=dev
AUTH_MODE=dev
TELEGRAM_BOT_TOKEN=<токен @zoshyt_dev_k_bot зі сховища>
WEBAPP_URL=https://dev-k.zoshyt.in.ua
# DB_URL / POSTGRES_PASSWORD — значення для локального compose, як в .env.example
```

Два режими роботи з UI:

- **Браузер (90% часу):** відкрий `http://localhost:5173`. Працює
  `AUTH_MODE=dev` — api приймає заголовок `X-Dev-User-Id` замість
  підпису Telegram. Швидко, з миттєвим оновленням при зміні коду (HMR).
- **Справжній Telegram (коли треба кнопки/тема/initData):** запусти
  `cloudflared tunnel run` і відкрий Mini App з чату
  `@zoshyt_dev_k_bot` (кнопка меню). Це той самий Vite, тільки через
  тунель.

---

## 5. Словник інструментів у репо

### Python: якість коду (запускаються всередині `make check`)

| Інструмент | Що робить |
|---|---|
| **ruff** | Лінтер і форматер в одному: єдиний стиль коду, ловить невикористані імпорти й підозрілі конструкції. Формат — автоматично при збереженні у VS Code. |
| **mypy** (strict) | Перевірка типів до запуску — наш «компілятор». Пишемо типізований код з першого дня. |
| **import-linter** | Перевіряє граф імпортів (конституцію) з розділу 2. |
| **pytest** | Тести: файли `test_*.py`, звичайні `assert`. `pytest-asyncio` — для async-тестів, `httpx` — HTTP-клієнт для тестів api. |
| **pre-commit** | Автоматично жене ruff перед кожним комітом. |

### Python: бібліотеки застосунку

| Бібліотека | Роль |
|---|---|
| **FastAPI** | HTTP-фреймворк api: роутери, валідація запитів/відповідей. |
| **uvicorn** | Сервер, який виконує FastAPI-застосунок. `--reload` у dev — перезапуск при зміні коду. |
| **SQLAlchemy 2.x** | Робота з БД: моделі таблиць і запити з Python. |
| **asyncpg** | Async-драйвер Postgres (мережевий шар під SQLAlchemy). |
| **Alembic** | Міграції схеми БД: кожна зміна структури — версіонований скрипт у репо; `alembic upgrade head` приводить будь-яку БД до актуального стану. |
| **aiogram 3.x** | Фреймворк Telegram-бота: хендлери команд, кнопки, long polling. |
| **APScheduler** | Планувальник джоб усередині процесу бота (нагадування о 09:00, heartbeat). |
| **pydantic / pydantic-settings** | Валідація даних через типи; читання і перевірка env-змінних у `config.py`. |
| **structlog** | Структуровані логи (у проді — JSON у stdout). |

### Frontend (miniapp/)

| Інструмент | Роль |
|---|---|
| **Vite** | Dev-сервер з миттєвим оновленням (HMR) і збирач продакшн-бандла. |
| **React + TypeScript** | UI-бібліотека + типи для JS. |
| **react-router** | Перемикання між 5 екранами всередині SPA. |
| **@telegram-apps/sdk-react** | Місток до Telegram: initData, кольори теми, MainButton/BackButton. |
| **ESLint + Prettier** | Лінт і формат для TS/React. |

Свідомо НЕ використовуємо: Redux та інші state-бібліотеки (стан тримає
бекенд), Next.js (SSR не потрібен), celery/redis (є APScheduler).

### Інфраструктура

| Інструмент | Роль |
|---|---|
| **make** | Словник команд: `make up` (Postgres), `make check` (усі перевірки — та сама команда, що жене CI), `make dev` (усе для розробки). |
| **Docker Compose** | Опис контейнерів: локально — Postgres; у проді — caddy + migrate + api + bot + postgres. |
| **cloudflared** | Тунель: публічний HTTPS для локального Vite (розділ 3.8). |
| **GitHub Actions** | CI: на кожен PR — `make check` + збірка фронта; CD: merge у main → деплой на сервер. |

---

## 6. Щоденний цикл роботи

1. `git switch -c` нова гілка від `main` (наприклад `feature/groups-screen`).
2. Пишеш код. `make check` локально — зелений.
3. `git push`, відкриваєш **Pull Request**.
4. CI проганяє перевірки; Сергій робить code review → approve.
5. Merge у `main`. (Напряму в `main` пушити неможливо — гілка захищена;
   це стосується всіх, включно з Сергієм.)
6. Merge у `main` автоматично деплоїться у прод.

Рішення «чому так, а не інакше» живуть у `docs/adr/` — короткі
пронумеровані документи. Перед зміною чогось фундаментального — глянь,
чи нема ADR про це; якщо реалізація суперечить ADR — питання
повертається в обговорення, а не обходиться в коді.

---

## 7. Чекліст «моє робоче місце готове»

- [ ] `uv run --python 3.12 python --version` → 3.12.x
- [ ] `node --version` → v22.x; `pnpm --version` відповідає
- [ ] `docker run --rm hello-world` — ок
- [ ] Репо склоновано по SSH; `git pull` працює без пароля
- [ ] `make up && make check` — зелено
- [ ] `make dev` → `http://localhost:5173` відкривається у браузері
- [ ] `cloudflared tunnel run` + тест з `http.server` →
      `https://dev-k.zoshyt.in.ua` відкривається
- [ ] Кнопка меню в `@zoshyt_dev_k_bot` відкриває ту саму сторінку
      всередині Telegram
- [ ] `.env` заповнений; токен — лише зі сховища

Застрягла на якомусь пункті — це не «щось не так зі мною», це діра в
README. Фіксуємо крок, що не спрацював, і правимо документ.
