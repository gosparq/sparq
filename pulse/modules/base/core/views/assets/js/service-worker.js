// sparQ Service Worker
// Provides offline support and caching for PWA functionality

const CACHE_VERSION = 'v18';

// Install event - skip waiting to activate immediately
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

// Activate event - clean up ALL old caches and take control
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => {
                return Promise.all(
                    keys
                        .filter((key) => key.startsWith('sparq-'))
                        .map((key) => {
                            console.log('[SW] Removing cache:', key);
                            return caches.delete(key);
                        })
                );
            })
            .then(() => self.clients.claim())
    );
});

// No fetch handler — let the browser handle all requests directly.
// This avoids caching issues that cause stale JS and slow page loads.

// Handle messages from clients
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    // Clear dynamic cache on logout
    if (event.data && event.data.type === 'CLEAR_CACHE') {
        event.waitUntil(
            caches.delete(DYNAMIC_CACHE).then(() => {
                console.log('[SW] Dynamic cache cleared');
            })
        );
    }
});

// -----------------------------------------------------------------------------
// Push Notification Support
// -----------------------------------------------------------------------------

// Handle incoming push notifications
self.addEventListener('push', (event) => {
    if (!event.data) {
        console.log('[SW] Push received but no data');
        return;
    }

    try {
        const data = event.data.json();
        console.log('[SW] Push notification received:', data.title);

        const options = {
            body: data.body || '',
            icon: data.icon || '/assets/images/pwa/icon-192x192.png',
            badge: '/assets/images/pwa/icon-192x192.png',
            data: {
                url: data.url || '/',
                badge_count: data.badge_count
            },
            tag: data.tag || 'sparq-notification',
            renotify: true,
            requireInteraction: true,  // Keep visible until user interacts (better for PWA)
            vibrate: [200, 100, 200],
            silent: false  // Ensure sound plays
        };

        const badgeCount = data.badge_count || 1;

        event.waitUntil(
            self.registration.showNotification(data.title || 'sparQ', options)
                .then(() => {
                    console.log('[SW] Notification shown successfully');
                    // Set badge (works on macOS PWA, Android/Chromium)
                    if (navigator.setAppBadge) {
                        console.log('[SW] Setting app badge to:', badgeCount);
                        return navigator.setAppBadge(badgeCount);
                    } else {
                        console.log('[SW] setAppBadge not available in service worker');
                    }
                })
                .catch((err) => {
                    console.error('[SW] Notification/badge error:', err);
                })
        );
    } catch (err) {
        console.error('[SW] Error processing push:', err);
    }
});

// Handle notification click - open the app to the relevant page
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    if (navigator.clearAppBadge) {
        navigator.clearAppBadge();
    }

    const targetPath = event.notification.data?.url || '/';
    const targetUrl = new URL(targetPath, self.location.origin).href;

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(async (clientList) => {
                for (const client of clientList) {
                    if (client.url.startsWith(self.location.origin)) {
                        await client.focus();
                        // Use postMessage so the page navigates itself via
                        // location.replace — avoids polluting the history stack
                        // with the service worker script URL.
                        client.postMessage({
                            type: 'NOTIFICATION_NAVIGATE',
                            url: targetUrl,
                        });
                        return;
                    }
                }

                if (clients.openWindow) {
                    return clients.openWindow(targetUrl);
                }
            })
    );
});
