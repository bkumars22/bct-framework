import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// GitHub Pages serves this app from a /bct-framework/ subpath and has no
// live backend (hence demo mode); local/Docker builds serve from root
// against a real backend. Only the explicit `--mode ghpages` build (used
// by the Pages workflow) gets the subpath base.
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  base: mode === 'ghpages' ? '/bct-framework/' : '/',
  server: {
    port: 3002,
    host: '0.0.0.0', // bind both IPv4 and IPv6 — default (bare "localhost") only bound IPv6 here
  },
}))
