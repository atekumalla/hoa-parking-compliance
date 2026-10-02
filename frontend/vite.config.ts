import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxies /api to the FastAPI backend during local dev so the browser sees
// everything as same-origin (no CORS setup needed, cookies work normally).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Use 127.0.0.1 explicitly — "localhost" resolves to ::1 on some
        // machines, and uvicorn only listens on the IPv4 loopback by default.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
