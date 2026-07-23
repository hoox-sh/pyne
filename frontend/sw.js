/* SuperChart Lite — service worker.
 *
 * Strategy:
 *   - App shell (HTML/CSS/JS at same origin) → cache-first, versioned cache.
 *   - CDN bundles (esm.sh, jsdelivr, unpkg) → cache-first with network fallback.
 *   - Same-origin /api/* (when CF Worker is configured) → network-first,
 *     fall back to cached response, then 503.
 *   - Everything else → network with cache fallback.
 *
 * The SW is intentionally permissive: if a request fails and nothing is
 * cached, we let the browser show its native error so the user is not
 * misled about offline capability.
 */

const VERSION = 'v1';
const SHELL_CACHE = `superchart-shell-${VERSION}`;
const RUNTIME_CACHE = `superchart-runtime-${VERSION}`;
const SHELL_ASSETS = [
    './',
    './index.html',
    './style.css',
    './manifest.webmanifest',
    './assets/icon-192.png',
    './assets/icon-512.png',
];

self.addEventListener('install', (event) => {
    event.waitUntil((async () => {
        const cache = await caches.open(SHELL_CACHE);
        await cache.addAll(SHELL_ASSETS.map((a) => new Request(a, { cache: 'reload' })));
        self.skipWaiting();
    })());
});

self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
        const names = await caches.keys();
        await Promise.all(
            names
                .filter((n) => n !== SHELL_CACHE && n !== RUNTIME_CACHE)
                .map((n) => caches.delete(n)),
        );
        await self.clients.claim();
    })());
});

function isShellAsset(url) {
    return url.origin === self.location.origin;
}

function isCdnAsset(url) {
    return /esm\.sh|jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com/.test(url.host);
}

function isApi(url) {
    return url.origin === self.location.origin && url.pathname.startsWith('/api/');
}

async function cacheFirst(req, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(req);
    if (cached) return cached;
    try {
        const res = await fetch(req);
        if (res && res.status === 200) cache.put(req, res.clone());
        return res;
    } catch (err) {
        if (cached) return cached;
        throw err;
    }
}

async function networkFirst(req, cacheName) {
    const cache = await caches.open(cacheName);
    try {
        const res = await fetch(req);
        if (res && res.status === 200) cache.put(req, res.clone());
        return res;
    } catch (err) {
        const cached = await cache.match(req);
        if (cached) return cached;
        return new Response(JSON.stringify({ status: 'error', code: 'OFFLINE', message: 'No network and no cached response.' }), {
            status: 503, headers: { 'Content-Type': 'application/json' },
        });
    }
}

self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return; // only cache GETs

    const url = new URL(req.url);

    if (isApi(url)) {
        event.respondWith(networkFirst(req, RUNTIME_CACHE));
        return;
    }

    if (isShellAsset(url) || isCdnAsset(url)) {
        event.respondWith(cacheFirst(req, isShellAsset(url) ? SHELL_CACHE : RUNTIME_CACHE));
        return;
    }

    // Other same-origin GETs (e.g. /api/* on a different host like the Flask dev
    // server) — passthrough, but opportunistically cache successful responses.
    event.respondWith((async () => {
        try {
            const res = await fetch(req);
            if (res && res.status === 200) {
                const cache = await caches.open(RUNTIME_CACHE);
                cache.put(req, res.clone());
            }
            return res;
        } catch (err) {
            const cache = await caches.open(RUNTIME_CACHE);
            const cached = await cache.match(req);
            if (cached) return cached;
            throw err;
        }
    })());
});

// Allow the page to trigger an immediate skip-waiting via postMessage.
self.addEventListener('message', (event) => {
    if (event.data === 'SKIP_WAITING') self.skipWaiting();
});
