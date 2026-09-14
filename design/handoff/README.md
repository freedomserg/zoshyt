# design/handoff — бандли з Claude Design

Сюди розпаковуються handoff-бандли з Claude Design: один бандл на екран,
`design/handoff/<screen>/` (HTML/CSS/JS, скріншоти станів, README з
інтентом). Zip не комітиться (.gitignore). П'ять екранів Mini App:
`groups`, `schedule`, `attendance`, `payments`, `debtors`.

Claude Code читає бандл РАЗОМ із відповідним ADR і реалізує екран у
`miniapp/src/screens/` + потрібні ендпоінти в `src/zoshyt/api/`.
Бандл — spec вигляду і станів, не код для копіювання.

Джерело правди для екранів — бандл у репо, не сесія в Claude Design.
Якщо реалізація змінила екран — прототип вирівнюється через `/design`.

## Обмеження Telegram Mini App, які кожен екран має поважати
- Кольори — з themeParams (`--tg-theme-*`, див. `miniapp/src/theme.ts`),
  не власна палітра; світла і темна тема — обидві.
- Safe-area (iOS): нічого важливого впритул до країв; не покладатися
  на 100vh.
- MainButton / BackButton Telegram — елементи UI екрана, не дублювати
  їх власними кнопками в тілі сторінки.
- Стан «відкрито в браузері без Telegram» (dev-режим): екран працює
  без themeParams і без нативних кнопок.
- Один екран = один маршрут react-router; нуль state-бібліотек.
- Дані: лише те, що є в journal (ADR-0009 — без адрес, дат народження,
  email); суми — у копійках, показ у гривнях.
