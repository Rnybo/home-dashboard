// sw.js — Familieoverblik service worker.
//
// SCOPE: static app-shell files only (html/css/js/vendor/icons). Never
// intercepts /api/* — that's cache.js's job (localStorage-based, its own TTL
// logic). Two caching layers fighting over the same data caused real bugs
// before (see frontend/js/CLAUDE.md); keeping them fully separate avoids that.
//
// STRATEGY: network-first, cache as fallback. NOT cache-first — Fully Kiosk's
// own caching already caused a multi-hour debugging saga (changes not showing
// up after deploy). This worker always tries the network first and only
// serves from cache when the network genuinely fails (offline). Slightly
// slower than cache-first on every load, but "deploy and it shows up" is more
// important here than shaving a few ms off a LAN request.

const CACHE_NAME = 'familieoverblik-shell-v1';

const SHELL_FILES = [
  '/', '/index.html', '/manifest.json',
  '/css/main.css', '/css/family.css',
  '/js/cache.js', '/js/globals.js', '/js/presence_edit.js', '/js/calendar.js',
  '/js/klasse.js', '/js/gallery.js', '/js/aula.js', '/js/auth.js', '/js/utils.js',
  '/js/cast.js', '/js/family.js', '/js/app.js',
  '/js/apps/tal.js', '/js/apps/nyheder.js', '/js/apps/regnespil.js',
  '/js/apps/huskespil.js', '/js/apps/stavespil.js',
  '/static/icons/icon-192.png', '/static/icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // Best-effort: one missing file shouldn't fail the whole install.
      Promise.all(SHELL_FILES.map((url) => cache.add(url).catch(() => {})))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Only handle same-origin GET requests, and never /api/* — let everything
  // else (API calls, cross-origin Aula/Google media, etc.) pass straight
  // through untouched.
  if (req.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) {
    return;
  }

  event.respondWith(
    fetch(req)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req))
  );
});
