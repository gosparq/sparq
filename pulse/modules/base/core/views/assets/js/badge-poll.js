/**
 * Badge Poll — lightweight unread count via fetch polling.
 *
 * Replaces the WebSocket-based badge-socket.js to free Gunicorn threads.
 * Polls /sync/chat/unread-count every 30s when tab is visible.
 * Skips if on the chat page (chat-socket.js handles badges there).
 */

(function() {
    'use strict';

    if (window.location.pathname.startsWith('/sync/chat')) return;

    var POLL_INTERVAL = 30000;
    var pollTimer = null;
    var unreadCount = window.INITIAL_CHAT_UNREAD_COUNT || 0;

    function updateBadges(count) {
        unreadCount = count;
        var shouldShow = count > 0;

        document.querySelectorAll('[data-chat-badge]').forEach(function(el) {
            el.style.display = shouldShow ? '' : 'none';
        });

        if ('setAppBadge' in navigator) {
            if (count > 0) {
                navigator.setAppBadge(count).catch(function() {});
            } else {
                navigator.clearAppBadge().catch(function() {});
            }
        }

        var baseTitle = document.title.replace(/^\(\d+\+?\)\s*/, '').replace(/^\(\u2022\)\s*/, '');
        document.title = count > 0 ? '(\u2022) ' + baseTitle : baseTitle;
    }

    function poll() {
        fetch('/sync/chat/unread-count')
            .then(function(r) { return r.ok ? r.json() : null; })
            .then(function(data) {
                if (data && typeof data.count === 'number') {
                    var oldCount = unreadCount;
                    updateBadges(data.count);
                    if (data.count > oldCount && window.NotificationSound) {
                        window.NotificationSound.play();
                    }
                    // Let the DM popup sync its own FAB badge from the same poll result.
                    document.dispatchEvent(new CustomEvent('chat-unread-sync', { detail: data }));
                }
            })
            .catch(function() {});
    }

    function startPolling() {
        if (pollTimer) return;
        poll();
        pollTimer = setInterval(poll, POLL_INTERVAL);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            startPolling();
        } else {
            stopPolling();
        }
    });

    if (document.readyState === 'complete') {
        if (document.visibilityState === 'visible') startPolling();
    } else {
        window.addEventListener('load', function() {
            if (document.visibilityState === 'visible') startPolling();
        });
    }

    window.updateChatBadges = updateBadges;

    document.addEventListener('DOMContentLoaded', function() {
        updateBadges(unreadCount);
    });
})();
