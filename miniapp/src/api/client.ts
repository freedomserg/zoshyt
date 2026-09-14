// ЄДИНЕ місце HTTP-викликів (README, розділ 2). Додає auth-заголовок.
// 401 = initData протух (~24 год) → «перевідкрий Mini App», не ретраї (CLAUDE.md).
import { authHeaders } from './auth'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path, { headers: authHeaders() })
  if (!response.ok) throw new ApiError(response.status, `${path}: ${response.status}`)
  return (await response.json()) as T
}
