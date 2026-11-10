import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

/**
 * Emit the list of hashed build assets so the service worker can precache the
 * lazy route chunks. Without it, an offline navigation to a page that was
 * never opened fails to load its JavaScript.
 */
function assetManifestPlugin() {
  return {
    name: 'greenhouse-asset-manifest',
    apply: 'build',
    writeBundle(options, bundle) {
      const outDir = options.dir || 'dist'
      const assets = Object.keys(bundle)
        .filter(file => file.startsWith('assets/'))
        .map(file => `/${file}`)
      fs.writeFileSync(
        path.join(outDir, 'asset-manifest.json'),
        JSON.stringify(assets, null, 2)
      )
    },
  }
}

// The dev server uses the same relative API paths as production and proxies
// them to the backend, so the bundle never hardcodes localhost.
export default defineConfig({
  plugins: [react(), assetManifestPlugin()],
  server: {
    // Bind the dev server to loopback by default. Exposing it on 0.0.0.0
    // gives the whole LAN access to source maps and HMR; set VITE_DEV_HOST
    // explicitly only when you need to test from a phone.
    host: process.env.VITE_DEV_HOST || '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/health': {
        target: process.env.VITE_DEV_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
  },
})
