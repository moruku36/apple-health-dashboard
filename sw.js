// ⚡ Service Worker Self-Destruct & Cache Buster
// すべてのキャッシュを完全に消去し、自分自身をアンレジストしてページを強制リフレッシュします

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            console.log('[ServiceWorker] Purging all caches completely:', keys);
            return Promise.all(keys.map((key) => caches.delete(key)));
        }).then(() => {
            return self.registration.unregister();
        }).then(() => {
            return self.clients.claim();
        }).then(() => {
            return self.clients.matchAll({ type: 'window' }).then((clients) => {
                clients.forEach((client) => {
                    // 最新のページへ強制リロード
                    client.navigate(client.url);
                });
            });
        })
    );
});

// すべてのリクエストをキャッシュせず直接ネットワークへ素通し
self.addEventListener('fetch', (event) => {
    event.respondWith(fetch(event.request));
});
