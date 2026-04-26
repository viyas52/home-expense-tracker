const CACHE_NAME = 'home-expenses-v1';
const ASSETS = [
    './',
    './index.html',
    './manifest.json',
    'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js'
];

// Install — cache shell assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(ASSETS))
            .then(() => self.skipWaiting())
    );
});

// Activate — clean old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

// Fetch — network first, fall back to cache
self.addEventListener('fetch', (event) => {
    // Skip non-GET and API/Firebase requests
    if (event.request.method !== 'GET') return;
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/parse') || url.hostname.includes('firestore')) return;

    event.respondWith(
        fetch(event.request)
            .then(response => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
