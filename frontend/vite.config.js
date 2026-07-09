import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-Proxy: /api -> lokales Backend (uvicorn auf :8000). In Prod splittet Caddy.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
