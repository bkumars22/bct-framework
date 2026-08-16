import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// GitHub Pages serves this app from a /bct-framework/ subpath and has no
// live backend (hence demo mode); local/Docker builds serve from root
// against a real backend. Only the explicit `--mode ghpages` build (used
// by the Pages workflow) gets the subpath base.

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/',
  server: {
    port: 3002,
    host: '0.0.0.0',
  },
})
