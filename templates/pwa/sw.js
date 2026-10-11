// Service worker do NaBandeja.
// Páginas e API: sempre do servidor (pedidos não podem vir de cache velho).
// /static/: cache primeiro (CSS, fontes, ícones), renovado a cada versão.
const CACHE_NAME = 'nabandeja-static-{{ nabandeja_version }}';
const PRECACHE = [
  '/static/css/app.css',
  '/static/vendor/bootstrap-icons/bootstrap-icons.min.css',
  '/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2',
  '/static/vendor/fonts/inter.woff2',
];

const OFFLINE_HTML = `<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sem conexão</title>
<body style="font-family:system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;margin:0;background:#f8fafc;color:#1e293b;text-align:center;padding:24px">
<div><h1 style="font-size:1.4rem">Sem conexão com o sistema</h1>
<p>Confira se o celular está no Wi-Fi do estabelecimento e se o computador do sistema está ligado.</p>
<button onclick="location.reload()" style="padding:12px 24px;border:0;border-radius:12px;background:#0f172a;color:#fff;font-weight:700">Tentar de novo</button></div>`;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)).catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        }
        return response;
      }))
    );
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(() => new Response(OFFLINE_HTML, { headers: { 'Content-Type': 'text/html; charset=utf-8' } }))
    );
  }
  // Demais requisições (API, mídia): direto para a rede, sem cache.
});
