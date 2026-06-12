/**
 * sparQ Push Notification Registration
 *
 * Handles browser push subscription management:
 * - Checks for browser support
 * - Shows enable notifications prompt (requires user click)
 * - Subscribes to push notifications
 * - Sends subscription to backend
 */

(function() {
    'use strict';

    // Check browser support
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        window.SPARQ_DEBUG && console.log('[Push] Push notifications not supported in this browser');
        return;
    }

    // Detect if running as installed PWA (standalone mode)
    const isPWA = window.matchMedia('(display-mode: standalone)').matches ||
                  window.navigator.standalone === true;  // iOS Safari
    window.SPARQ_DEBUG && console.log('[Push] Running in PWA mode:', isPWA);

    // Store VAPID key once fetched
    let vapidPublicKey = null;

    // Wait for service worker to be ready
    navigator.serviceWorker.ready.then(async function(registration) {
        window.SPARQ_DEBUG && console.log('[Push] Service worker ready, checking subscription status...');

        try {
            // Check if already subscribed
            const existingSubscription = await registration.pushManager.getSubscription();
            if (existingSubscription) {
                window.SPARQ_DEBUG && console.log('[Push] Already subscribed, syncing with backend');
                await sendSubscriptionToBackend(existingSubscription);
                return;
            }

            // Get VAPID public key from server
            const response = await fetch('/api/push/vapid-public-key');
            if (!response.ok) {
                if (response.status === 404) {
                    window.SPARQ_DEBUG && console.log('[Push] Push notifications not configured on server');
                    return;
                }
                throw new Error('Failed to get VAPID public key: ' + response.status);
            }

            const data = await response.json();
            vapidPublicKey = data.publicKey;

            if (!vapidPublicKey) {
                window.SPARQ_DEBUG && console.log('[Push] No VAPID public key in response');
                return;
            }

            window.SPARQ_DEBUG && console.log('[Push] VAPID key received, permission status:', Notification.permission);

            // Check current permission status
            if (Notification.permission === 'granted') {
                // Already have permission, subscribe directly
                window.SPARQ_DEBUG && console.log('[Push] Permission already granted, subscribing...');
                await subscribeToPush(registration);
            } else if (Notification.permission === 'default') {
                // In PWA mode, request permission more directly (user chose to install the app)
                if (isPWA) {
                    window.SPARQ_DEBUG && console.log('[Push] PWA mode - requesting permission directly');
                    // Clear any previous dismissal since user installed the app
                    localStorage.removeItem('sparq_push_dismissed');
                    await requestPermissionAndSubscribe(registration);
                } else {
                    // In browser, show the enable banner
                    window.SPARQ_DEBUG && console.log('[Push] Permission not yet requested, showing banner');
                    showEnableNotificationsBanner(registration);
                }
            } else {
                window.SPARQ_DEBUG && console.log('[Push] Notifications are blocked by user');
            }

        } catch (error) {
            console.error('[Push] Error during push setup:', error);
        }
    });

    /**
     * Show a banner prompting user to enable notifications
     */
    function showEnableNotificationsBanner(registration) {
        // Don't show if user dismissed it before (stored in localStorage)
        if (localStorage.getItem('sparq_push_dismissed') === 'true') {
            window.SPARQ_DEBUG && console.log('[Push] User previously dismissed notification prompt');
            return;
        }

        const banner = document.createElement('div');
        banner.id = 'push-notification-banner';
        banner.innerHTML = `
            <div style="position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#1e1e2e;color:white;padding:12px 20px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.3);z-index:10000;display:flex;align-items:center;gap:12px;max-width:90%;font-size:14px;">
                <i class="fas fa-bell" style="font-size:18px;color:#a78bfa;"></i>
                <span>Get notified when you receive messages</span>
                <button id="push-enable-btn" style="background:#7c3aed;color:white;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;font-weight:500;">Enable</button>
                <button id="push-dismiss-btn" style="background:transparent;color:#888;border:none;padding:8px;cursor:pointer;font-size:18px;">&times;</button>
            </div>
        `;
        document.body.appendChild(banner);

        document.getElementById('push-enable-btn').addEventListener('click', async function() {
            banner.remove();
            await requestPermissionAndSubscribe(registration);
        });

        document.getElementById('push-dismiss-btn').addEventListener('click', function() {
            banner.remove();
            localStorage.setItem('sparq_push_dismissed', 'true');
        });
    }

    /**
     * Request permission and subscribe (called from user click)
     */
    async function requestPermissionAndSubscribe(registration) {
        try {
            window.SPARQ_DEBUG && console.log('[Push] Requesting notification permission...');
            const permission = await Notification.requestPermission();
            window.SPARQ_DEBUG && console.log('[Push] Permission result:', permission);

            if (permission === 'granted') {
                await subscribeToPush(registration);
            } else {
                window.SPARQ_DEBUG && console.log('[Push] Permission denied by user');
            }
        } catch (error) {
            console.error('[Push] Error requesting permission:', error);
        }
    }

    /**
     * Subscribe to push notifications
     */
    async function subscribeToPush(registration) {
        try {
            window.SPARQ_DEBUG && console.log('[Push] Subscribing to push notifications...');

            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
            });

            window.SPARQ_DEBUG && console.log('[Push] Subscribed successfully');
            await sendSubscriptionToBackend(subscription);

        } catch (error) {
            console.error('[Push] Error subscribing:', error);
        }
    }

    /**
     * Send subscription to backend for storage
     */
    async function sendSubscriptionToBackend(subscription) {
        try {
            const response = await fetch('/api/push/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(subscription.toJSON())
            });

            if (!response.ok) {
                throw new Error('Failed to save subscription: ' + response.status);
            }

            window.SPARQ_DEBUG && console.log('[Push] Subscription saved to backend');
        } catch (error) {
            console.error('[Push] Error saving subscription:', error);
        }
    }

    /**
     * Convert VAPID public key from base64 URL-safe to Uint8Array
     */
    function urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }

        return outputArray;
    }

    /**
     * Manually trigger push registration (can be called from settings)
     */
    window.sparqEnablePushNotifications = async function() {
        const registration = await navigator.serviceWorker.ready;
        await requestPermissionAndSubscribe(registration);
    };

    /**
     * Unsubscribe from push notifications
     */
    window.sparqPushUnsubscribe = async function() {
        try {
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();

            if (!subscription) {
                window.SPARQ_DEBUG && console.log('[Push] Not subscribed');
                return true;
            }

            await subscription.unsubscribe();

            await fetch('/api/push/unsubscribe', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ endpoint: subscription.endpoint })
            });

            window.SPARQ_DEBUG && console.log('[Push] Unsubscribed successfully');
            return true;
        } catch (error) {
            console.error('[Push] Error unsubscribing:', error);
            return false;
        }
    };

    /**
     * Reset the dismissed state (for testing)
     */
    window.sparqResetPushPrompt = function() {
        localStorage.removeItem('sparq_push_dismissed');
        window.SPARQ_DEBUG && console.log('[Push] Prompt reset, refresh page to see banner');
    };

    /**
     * Test badge API support (for debugging)
     */
    window.sparqTestBadge = async function(count) {
        window.SPARQ_DEBUG && console.log('[Badge] Testing badge API...');
        window.SPARQ_DEBUG && console.log('[Badge] setAppBadge available:', typeof navigator.setAppBadge);
        window.SPARQ_DEBUG && console.log('[Badge] clearAppBadge available:', typeof navigator.clearAppBadge);

        if (!navigator.setAppBadge) {
            window.SPARQ_DEBUG && console.log('[Badge] Badge API not supported on this device/browser');
            return false;
        }

        try {
            if (count === 0) {
                await navigator.clearAppBadge();
                window.SPARQ_DEBUG && console.log('[Badge] Badge cleared');
            } else {
                await navigator.setAppBadge(count || undefined);
                window.SPARQ_DEBUG && console.log('[Badge] Badge set to:', count || 'dot');
            }
            return true;
        } catch (err) {
            console.error('[Badge] Error:', err.name, err.message);
            return false;
        }
    };

    /**
     * Sync app badge when app becomes visible.
     * Uses actual unread count from chat state if available.
     */
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            // If we have chat state, sync badge with actual count
            if (window.syncChatBadge) {
                window.syncChatBadge();
            } else if (window.getChatUnreadCount) {
                var count = window.getChatUnreadCount();
                if (count === 0 && navigator.clearAppBadge) {
                    navigator.clearAppBadge().catch(function() {});
                } else if (count > 0 && navigator.setAppBadge) {
                    navigator.setAppBadge(count).catch(function() {});
                }
            }
            // Fallback: if not in chat module, don't change badge
        }
    });

})();
