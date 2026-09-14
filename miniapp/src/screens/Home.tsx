import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'
import { insideTelegram } from '../telegram'

export function Home() {
  const [health, setHealth] = useState<string>('…')

  useEffect(() => {
    apiGet<{ status: string }>('/health')
      .then((r) => setHealth(r.status))
      .catch((e: Error) => setHealth(e.message))
  }, [])

  return (
    <main>
      <h1>Zoshyt</h1>
      <p>Режим: {insideTelegram ? 'Telegram' : 'браузер (dev)'}</p>
      <p>api /health: {health}</p>
    </main>
  )
}
