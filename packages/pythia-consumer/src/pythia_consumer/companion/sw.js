/* PYTHIA Companion service worker — cache-first offline shell.
 *
 * Registers only on secure origins (localhost or https). Over plain-LAN
 * http on iPhone the browser refuses registration — the app still loads
 * and verifies client-side, just without an offline cache. That is a
 * platform constraint, not a stub: say so in the UI rather than faking it.
 */
const CACHE = "pythia-companion-v1";
const ASSETS = ["./", "index.html", "verify.js", "manifest.webmanifest", "icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then((hit) =>
      hit || fetch(e.request).then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return resp;
      }))
  );
});
