self.addEventListener('install', event => {
    event.waitUntil(
      caches.open('v1').then(cache =>
        cache.addAll([
          '/',
          '/static/css/home.css',
          '/static/js/home.js',
          '/static/brand/favicon-192.jpg'
        ])
      )
    );
  });
  
  self.addEventListener('fetch', event => {
    event.respondWith(
      caches.match(event.request).then(response => response || fetch(event.request))
    );
  });
  