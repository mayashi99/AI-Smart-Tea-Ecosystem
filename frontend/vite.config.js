import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
<<<<<<< HEAD
  plugins: [react()],
  appType: 'spa',
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
=======
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/component02': {
>>>>>>> feature/yield-intelligence
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
