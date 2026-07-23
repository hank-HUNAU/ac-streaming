const CACHE_NAME = 'acspeaker-v1';
const STATIC_ASSETS = [
  './',
  './index.html',
  './data/papers.json',
  './data/glossary.json',
];

// Install: cache static assets
self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      console.log('Caching static assets');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames
          .filter(function(name) { return name !== CACHE_NAME; })
          .map(function(name) { return caches.delete(name); })
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first for data, cache-first for API responses
self.addEventListener('fetch', function(event) {
  var url = event.request.url;

  // Cache static data JSON
  if (url.includes('/data/') && url.endsWith('.json')) {
    event.respondWith(
      caches.match(event.request).then(function(cached) {
        if (cached) return cached;
        return fetch(event.request).then(function(response) {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          var responseToCache = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, responseToCache);
          });
          return response;
        }).catch(function() {
          return cached || new Response('Offline', {status: 503});
        });
      })
    );
    return;
  }

  // Cache audio files
  if (url.includes('/audio/')) {
    event.respondWith(
      caches.match(event.request).then(function(cached) {
        if (cached) return cached;
        return fetch(event.request).then(function(response) {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          var responseToCache = response.clone();
          caches.open(CACHE_NAME).then(function(cache) {
            cache.put(event.request, responseToCache);
          });
          return response;
        }).catch(function() {
          return cached || new Response('Audio unavailable offline', {status: 503});
        });
      })
    );
    return;
  }

  // Default: network first
  event.respondWith(fetch(event.request));
});
