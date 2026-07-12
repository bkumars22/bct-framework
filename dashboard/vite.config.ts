import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3002,
    host: '0.0.0.0', // bind both IPv4 and IPv6 — default (bare "localhost") only bound IPv6 here
  },
})
