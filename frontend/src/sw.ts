/// <reference lib="webworker" />
// ── Service Worker for SolarIntel v2 ─────────────────────────────────────────
// Strategy:
//   - Static assets  → Cache-first (versioned cache name)
//   - /api/ routes   → Network-first with 5s timeout
//   - Navigation     → Network-first, fallback to offline page

export type {} // Make this a module so "self" doesn't conflict with Window

const sw = self as unknown as ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>
}

const CACHE_VERSION = 'v1'
const STATIC_CACHE = `solarintel-static-${CACHE_VERSION}`
const RUNTIME_CACHE = `solarintel-runtime-${CACHE_VERSION}`

// __WB_MANIFEST is injected by vite-plugin-pwa at build time with all
// precacheable asset URLs. We merge it with our manual static assets.
const WB_MANIFEST = sw.__WB_MANIFEST

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  ...WB_MANIFEST.map((entry) => entry.url),
]

// ── Install ───────────────────────────────────────────────────────────────────

sw.addEventListener('install', (event: ExtendableEvent) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
  )
  void sw.skipWaiting()
})

// ── Activate ──────────────────────────────────────────────────────────────────

sw.addEventListener('activate', (event: ExtendableEvent) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== STATIC_CACHE && key !== RUNTIME_CACHE)
          .map((key) => caches.delete(key)),
      ),
    ),
  )
  void sw.clients.claim()
})

// ── Fetch ─────────────────────────────────────────────────────────────────────

sw.addEventListener('fetch', (event: FetchEvent) => {
  const { request } = event
  const url = new URL(request.url)

  // Skip non-GET and cross-origin
  if (request.method !== 'GET' || url.origin !== sw.location.origin) return

  // API calls → network-first, no cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request))
    return
  }

  // Static assets → cache-first
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirst(request))
    return
  }

  // Navigation → network-first with offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(navigateFetch(request))
  }
})

// ── Strategy helpers ──────────────────────────────────────────────────────────

async function cacheFirst(request: Request): Promise<Response> {
  const cached = await caches.match(request)
  if (cached !== undefined) return cached

  const response = await fetch(request)
  if (response.ok) {
    const cache = await caches.open(RUNTIME_CACHE)
    void cache.put(request, response.clone())
  }
  return response
}

async function networkFirst(request: Request): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 5_000)

  try {
    const response = await fetch(request, { signal: controller.signal })
    clearTimeout(timeoutId)
    return response
  } catch {
    clearTimeout(timeoutId)
    return new Response(
      JSON.stringify({ detail: 'Réseau indisponible' }),
      { status: 503, headers: { 'Content-Type': 'application/json' } },
    )
  }
}

async function navigateFetch(request: Request): Promise<Response> {
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE)
      void cache.put(request, response.clone())
    }
    return response
  } catch {
    const cached = await caches.match('/index.html')
    if (cached !== undefined) return cached
    const offline = await caches.match('/offline.html')
    return offline ?? new Response('Hors ligne', { status: 503 })
  }
}

function isStaticAsset(pathname: string): boolean {
  return /\.(js|css|png|jpg|jpeg|svg|gif|webp|woff2?|ttf|ico)$/.test(pathname)
}
