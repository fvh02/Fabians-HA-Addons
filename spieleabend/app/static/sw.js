/* Spieleabend service worker: lets the page be installed as an app. Always asks the server
   first (games are live), and only falls back to a cached copy of the static files offline. */
const CACHE = "spieleabend-v1";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.endsWith("/ws")) return;
  e.respondWith(fetch(e.request).then(res => {
    if (res.ok && url.pathname.includes("/static/")) {
      const copy = res.clone();
      caches.open(CACHE).then(c => c.put(e.request, copy));
    }
    return res;
  }).catch(() => caches.match(e.request).then(hit => hit || new Response(
    "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><body style='font-family:system-ui;background:#0b0a1f;color:#fff;display:grid;place-items:center;height:100vh;margin:0;text-align:center'><div><h2>Keine Verbindung</h2><p>Spieleabend ist gerade nicht erreichbar.</p></div>",
    { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }))));
});
