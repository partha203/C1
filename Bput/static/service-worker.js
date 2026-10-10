// CampusOne service worker — caches static assets for offline/low-bandwidth use.
const CACHE_NAME = "campusone-cache-v1";
const STATIC_ASSETS = [
  "/static/css/style.css",
  "/static/js/main.js",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(STATIC_ASSETS).catch(function () {
        // Best-effort caching; don't fail install if an asset is missing
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; }).map(function (k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", function (event) {
  const req = event.request;
  if (req.method !== "GET") return; // never cache POST (form submissions)

  // Static assets: cache-first
  if (req.url.includes("/static/")) {
    event.respondWith(
      caches.match(req).then(function (cached) {
        return cached || fetch(req).then(function (res) {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then(function (cache) { cache.put(req, resClone); });
          return res;
        });
      })
    );
    return;
  }

  // Pages: network-first, fall back to cache if offline
  event.respondWith(
    fetch(req).catch(function () {
      return caches.match(req);
    })
  );
});
