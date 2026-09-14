import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Слухати на 0.0.0.0 — потрібно для cloudflared-тунелю (README, 3.8).
    host: true,
    allowedHosts: ['dev-s.zoshyt.in.ua', 'dev-k.zoshyt.in.ua'],
    // У dev сторінку віддає Vite, а api живе на :8000 — проксі, щоб фронт
    // ходив на той самий origin, як і в prod за Caddy.
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
