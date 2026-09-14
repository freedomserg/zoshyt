# ADR-0012 — Лінтер miniapp: oxlint замість eslint

Статус: accepted (2026-09-14). Уточнює ADR-0010 (пункт «eslint + prettier»).

## Контекст
ADR-0010 зафіксував для miniapp «eslint + prettier». На день скаффолду
(вересень 2026) шаблон `pnpm create vite --template react-ts` кладе
oxlint замість eslint: той самий набір правил для React/TS
(rules-of-hooks, only-export-components, typescript-плагін), реалізація
на Rust, конфіг — один `.oxlintrc.json` без плагінів і парсерів.
eslint у шаблоні більше не пропонується. Ставити eslint означало б
чотири пакети й конфіг руками заради тієї самої ролі.

## Рішення
Лінтер TS/React у miniapp — oxlint, як його дає шаблон Vite.
Форматер — prettier (без змін). `pnpm -C miniapp lint` — обов'язкова
перевірка в CI поруч із `pnpm build`.

## Альтернативи (відкинуті)
- eslint + typescript-eslint + plugin-react-hooks + plugin-react-refresh:
  відповідає букві ADR-0010, але це конфіг з пам'яті, повільніший
  лінт у CI і додаткова сутність для [К] без нової користі.
- Без лінтера, лише tsc: не ловить rules-of-hooks.

## Наслідки
- ADR-0010 не редагується; пункт про eslint читати як «лінтер TS/React».
- Якщо oxlint колись не покриє потрібне правило (наприклад, для
  доступності) — окремий ADR, не тихий перехід.

## Для Claude Code
Конфіг лінтера — `miniapp/.oxlintrc.json`. eslint у miniapp не додавати.
Нові правила — лише ті, що є в oxlint; інакше — ADR.
