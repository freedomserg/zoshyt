// themeParams Telegram → CSS-змінні --tg-theme-* (bg-color, text-color, hint-color, …).
// Поза Telegram змінні не з'являються — index.css має fallback-значення.
import { bindThemeParamsCssVars, mountThemeParamsSync } from '@telegram-apps/sdk-react'

export function applyTelegramTheme(): void {
  if (mountThemeParamsSync.isAvailable()) mountThemeParamsSync()
  if (bindThemeParamsCssVars.isAvailable()) bindThemeParamsCssVars()
}
