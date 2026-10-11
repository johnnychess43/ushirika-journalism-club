const CACHE_NAME = "ushirika-shell-v1";
const APP_ICON = "/static/ushirika-icon.svg";
const MANIFEST = "/static/manifest.webmanifest";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll([APP_ICON, MANIFEST]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  // Never cache pages or responses that may contain login, account, or financial information.
  if (request.mode === "navigate" || /\/(login|register|dashboard|admin|payment|patron-centre|logout)(\/|$)/.test(url.pathname)) {
    event.respondWith(fetch(request).catch(() => new Response(
      "<!doctype html><html lang=\"en\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta charset=\"utf-8\"><title>Ushirika offline</title><body style=\"font:16px Arial,sans-serif;max-width:36rem;margin:12vh auto;padding:1.5rem;color:#172b25\"><h1>You’re offline</h1><p>Ushirika needs an internet connection to securely load member pages. Reconnect and try again.</p><p><a href=\"/login\">Return to member login</a></p></body></html>",
      { status: 503, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } }
    )));
    return;
  }

  if (url.pathname === APP_ICON || url.pathname === MANIFEST) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request))
    );
  }
});
