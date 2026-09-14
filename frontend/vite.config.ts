import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API is proxied so browser code only ever uses relative /api URLs.
// That keeps the preview host, localhost dev and production same-origin
// deployments all working without hardcoding a backend origin.
const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: {
      '/api': { target: apiTarget, changeOrigin: true },
    },
    // Behind the sandbox HTTPS preview proxy the browser reaches the dev server
    // through a wss reverse proxy, so the HMR client must use wss + the proxy's
    // clientPort. VITE_HMR_CLIENT_PORT overrides the port; SANDBOX_PREVIEW_HMR=1
    // enables it explicitly so local `http://localhost:5173` runs are not forced
    // onto wss://localhost:443 (which nothing listens on, producing a console
    // error storm and no live reload).
    ...(process.env.SANDBOX_PREVIEW_HMR || process.env.VITE_HMR_CLIENT_PORT
      ? {
          hmr: {
            protocol: 'wss' as const,
            clientPort: Number(process.env.VITE_HMR_CLIENT_PORT || 443),
          },
        }
      : {}),
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    allowedHosts: true,
    proxy: { '/api': { target: apiTarget, changeOrigin: true } },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
} as any)
