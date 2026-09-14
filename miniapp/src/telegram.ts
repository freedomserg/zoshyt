// Тонкий шар над @telegram-apps/sdk-react (ADR-0001). Компоненти екранів
// SDK напряму не імпортують — лише цей модуль, theme.ts і api/auth.ts.
import { init, isTMA, retrieveRawInitData } from '@telegram-apps/sdk-react'

/** true — відкрито всередині Telegram; false — звичайний браузер (dev-режим). */
export const insideTelegram: boolean = isTMA()

/** Ініціалізація SDK. Поза Telegram — no-op: init() без середовища кидає помилку. */
export function initTelegram(): void {
  if (insideTelegram) init()
}

/** Сирий initData для заголовка Authorization. undefined поза Telegram. */
export function rawInitData(): string | undefined {
  return insideTelegram ? retrieveRawInitData() : undefined
}
