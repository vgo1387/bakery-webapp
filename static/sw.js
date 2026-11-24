/* Service Worker — کش برای کار آفلاین، با اولویت نسخه جدید */
const CACHE = 'bakery-v4';
const CORE = [
    '/',
    '/login',
    '/static/manifest.json',
    '/static/css/style.css',
    '/static/js/main.js',
    '/static/leaflet/leaflet.css',
    '/static/leaflet/leaflet.js'
];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (e) => {
    const url = e.request.url;
    // فقط صفحه‌ها و فایل‌های استاتیک GET را کش می‌کنیم
    if (e.request.method !== 'GET') return;
    if (!url.startsWith(self.location.origin)) return;
    // درخواست‌های API همیشه از شبکه (داده زنده)
    if (url.includes('/api/')) return;

    // استراتژی network-first: اول شبکه، در قطعی اینترنت از کش
    e.respondWith(
        fetch(e.request).then((resp) => {
            if (resp && resp.status === 200) {
                const copy = resp.clone();
                caches.open(CACHE).then((c) => c.put(e.request, copy));
            }
            return resp;
        }).catch(() =>
            caches.match(e.request).then((cached) => cached || Response.error())
        )
    );
});
