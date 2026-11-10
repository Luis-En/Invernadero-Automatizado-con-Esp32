/* Invernadero Automatizado — service worker
   --------------------------------------------------------------------------
   Strategy:
   - App shell / navigations: network first, cached shell as fallback.
   - Hashed build assets and icons: cache first, then network + cache.
   - API and health checks: always network (telemetry must never be stale).
   - Web Push: render irrigation alerts and focus the app on click.
*/

const VERSION = 'invernadero-v4'
const SHELL_CACHE = `${VERSION}-shell`
const ASSET_CACHE = `${VERSION}-assets`

const SHELL = [
  '/',
  '/offline.html',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/favicon.svg',
]

async function precacheBuildAssets() {
  try {
    const response = await fetch('/asset-manifest.json', { cache: 'no-store' })
    if (!response.ok) return
    const assets = await response.json()
    if (!Array.isArray(assets)) return
    const cache = await caches.open(ASSET_CACHE)
    await Promise.all(
      assets.map(url =>
        cache.add(new Request(url, { cache: 'reload' })).catch(() => null)
      )
    )
  } catch {
    /* Offline install: the online navigations will fill the cache later. */
  }
}

/* Every deploy gets new hashed filenames. The SW version constant does not
   change on ordinary deploys, so refresh the list from the build manifest and
   prune assets from older builds instead of growing the cache forever. */
let assetRefresh = null
let lastAssetRefresh = 0
function refreshAssetCache({ force = false } = {}) {
  if (!force && Date.now() - lastAssetRefresh < 10 * 60 * 1000) {
    return Promise.resolve()
  }
  if (assetRefresh) return assetRefresh

  assetRefresh = (async () => {
    try {
      const response = await fetch('/asset-manifest.json', { cache: 'no-store' })
      if (!response.ok) return
      const assets = await response.json()
      if (!Array.isArray(assets)) return

      const cache = await caches.open(ASSET_CACHE)
      const keep = new Set(assets)
      await Promise.all(
        assets.map(async url => {
          if (await cache.match(url)) return
          await cache
            .add(new Request(url, { cache: 'reload' }))
            .catch(() => null)
        })
      )

      for (const request of await cache.keys()) {
        const path = new URL(request.url).pathname
        if (path.startsWith('/assets/') && !keep.has(path)) {
          await cache.delete(request)
        }
      }
      lastAssetRefresh = Date.now()
    } catch {
      /* Offline or a half-written manifest: try again next navigation. */
    } finally {
      assetRefresh = null
    }
  })()

  return assetRefresh
}

self.addEventListener('install', event => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE)
      // One missing file must not abort the whole install.
      await Promise.all(SHELL.map(url => cache.add(url).catch(() => null)))
      // Lazy route chunks are not referenced by index.html; precache them so
      // every page works offline after the first successful install.
      await precacheBuildAssets()
    })()
  )
})

self.addEventListener('activate', event => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(
        keys
          .filter(key => key !== SHELL_CACHE && key !== ASSET_CACHE)
          .map(key => caches.delete(key))
      )
      if (self.registration.navigationPreload) {
        await self.registration.navigationPreload.disable()
      }
      await self.clients.claim()
    })()
  )
})

self.addEventListener('message', event => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting()
})

async function networkFirst(request, event) {
  const cache = await caches.open(SHELL_CACHE)
  try {
    const response = await fetch(request)
    if (response.ok) {
      cache.put(request, response.clone())
      // A successful navigation is the right moment to notice a new build.
      if (event && request.mode === 'navigate') {
        event.waitUntil(refreshAssetCache())
      }
    }
    return response
  } catch {
    const cached = await cache.match(request, { ignoreSearch: true })
    if (cached) return cached
    const shell = await cache.match('/')
    if (shell) return shell
    return cache.match('/offline.html')
  }
}

async function cacheFirst(request) {
  const cache = await caches.open(ASSET_CACHE)
  const cached = await cache.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) cache.put(request, response.clone())
  return response
}

self.addEventListener('fetch', event => {
  const { request } = event
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  // Live data must never be served from cache.
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') return

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request, event))
    return
  }

  if (
    url.pathname.startsWith('/assets/') ||
    url.pathname.startsWith('/icons/') ||
    /\.(?:css|js|png|svg|jpg|jpeg|webp|woff2?)$/.test(url.pathname)
  ) {
    event.respondWith(cacheFirst(request))
  }
})

self.addEventListener('push', event => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { body: event.data ? event.data.text() : '' }
  }

  const title = payload.title || 'Invernadero Automatizado'
  const options = {
    body: payload.body || 'Hay una actualización del invernadero.',
    icon: payload.icon || '/icons/icon-192.png',
    badge: payload.badge || '/icons/badge-72.png',
    tag: payload.tag || 'irrigation-needed',
    renotify: true,
    vibrate: [180, 80, 180],
    // A dry-soil alert stays on screen until the user acts on it.
    requireInteraction: Boolean(payload.critical),
    timestamp: Date.now(),
    data: { url: payload.url || '/', critical: Boolean(payload.critical) },
    actions: [{ action: 'open', title: 'Abrir invernadero' }],
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

/* The push service can rotate an endpoint (common after long idle periods or
   a browser update). Ask an open client to re-subscribe and store the new
   endpoint; the page owns the VAPID key and the authenticated API call. */
self.addEventListener('pushsubscriptionchange', event => {
  event.waitUntil(
    (async () => {
      const clients = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      })
      for (const client of clients) {
        client.postMessage({
          type: 'PUSH_SUBSCRIPTION_CHANGED',
          oldEndpoint: event.oldSubscription?.endpoint || null,
        })
      }
    })()
  )
})

self.addEventListener('notificationclick', event => {
  event.notification.close()
  const target = event.notification.data?.url || '/'

  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      })
      for (const client of windows) {
        if (client.url.startsWith(self.location.origin)) {
          await client.focus()
          if ('navigate' in client) {
            try {
              await client.navigate(target)
            } catch {
              /* focus is enough if navigation is blocked */
            }
          }
          return
        }
      }
      await self.clients.openWindow(target)
    })()
  )
})
