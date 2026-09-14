// Єдине місце на фронті, що знає про initData (CLAUDE.md, ADR-0001).
// У Telegram: Authorization: tma <initData>. У браузері: X-Dev-User-Id (AUTH_MODE=dev на api).
import { rawInitData } from '../telegram'

const DEV_USER_ID = '1'

export function authHeaders(): Record<string, string> {
  const initData = rawInitData()
  if (initData) return { Authorization: `tma ${initData}` }
  return { 'X-Dev-User-Id': DEV_USER_ID }
}
