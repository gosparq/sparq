/**
 * Desktop Browser Badge Utility
 *
 * Updates document title and favicon to show unread message count.
 * Works in Chrome, Safari, Firefox and other desktop browsers.
 *
 * Title format: (3) Chat - sparQOne
 * Favicon: Red badge circle with count overlay
 */

const BadgeUtils = {
    originalTitle: null,
    canvas: null,
    baseIconLoaded: false,
    baseIcon: null,
    initialized: false,

    /**
     * Initialize the badge utility.
     * Call once on page load.
     */
    init() {
        if (this.initialized) return;
        this.initialized = true;

        this.originalTitle = document.title;
        this.canvas = document.createElement('canvas');
        this.canvas.width = 32;
        this.canvas.height = 32;

        // Get icon URL from existing apple-touch-icon link (uses Flask's url_for)
        var appleIcon = document.querySelector("link[rel='apple-touch-icon']");
        if (!appleIcon) {
            return;
        }

        // Preload base icon
        this.baseIcon = new Image();
        this.baseIcon.onload = () => { this.baseIconLoaded = true; };
        this.baseIcon.onerror = () => { this.baseIconLoaded = false; };
        this.baseIcon.src = appleIcon.href;
    },

    /**
     * Update both title and favicon badges.
     * @param {number} count - Total unread message count
     */
    updateBadge(count) {
        this.updateTitle(count);
        this.updateFavicon(count);
        this.updatePwaBadge(count);
    },

    /**
     * Update PWA app badge (dock/taskbar icon).
     * Works when app is installed as PWA on macOS, Windows, Android.
     * @param {number} count - Unread count
     */
    updatePwaBadge(count) {
        const isPWA = window.matchMedia('(display-mode: standalone)').matches ||
                      window.navigator.standalone === true;
        window.SPARQ_DEBUG && console.log('[Badge] updatePwaBadge called:', { count, isPWA, hasSetAppBadge: !!navigator.setAppBadge });

        if (!navigator.setAppBadge) {
            window.SPARQ_DEBUG && console.log('[Badge] setAppBadge API not available');
            return;
        }

        if (count > 0) {
            navigator.setAppBadge(count)
                .then(() => window.SPARQ_DEBUG && console.log('[Badge] App badge set to:', count))
                .catch((err) => window.SPARQ_DEBUG && console.log('[Badge] Failed to set badge:', err.message));
        } else {
            if (navigator.clearAppBadge) {
                navigator.clearAppBadge()
                    .then(() => window.SPARQ_DEBUG && console.log('[Badge] App badge cleared'))
                    .catch((err) => window.SPARQ_DEBUG && console.log('[Badge] Failed to clear badge:', err.message));
            }
        }
    },

    /**
     * Update document title with unread count.
     * @param {number} count - Unread count
     */
    updateTitle(count) {
        if (!this.originalTitle) return;
        // Strip any existing badge from title
        const baseTitle = this.originalTitle.replace(/^\(\d+\+?\)\s*/, '');
        document.title = count > 0 ? `(${count > 99 ? '99+' : count}) ${baseTitle}` : baseTitle;
    },

    /**
     * Update favicon with badge overlay.
     * @param {number} count - Unread count
     */
    updateFavicon(count) {
        if (!this.baseIconLoaded || !this.canvas) return;

        const ctx = this.canvas.getContext('2d');
        ctx.clearRect(0, 0, 32, 32);
        ctx.drawImage(this.baseIcon, 0, 0, 32, 32);

        if (count > 0) {
            // Red badge circle (top-right)
            ctx.fillStyle = '#ef4444';
            ctx.beginPath();
            ctx.arc(24, 8, 8, 0, 2 * Math.PI);
            ctx.fill();

            // White count text
            ctx.fillStyle = 'white';
            ctx.font = 'bold 10px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(count > 99 ? '99+' : String(count), 24, 8);
        }

        this.setFavicon(this.canvas.toDataURL());
    },

    /**
     * Set the page favicon.
     * @param {string} href - Data URL or path to icon
     */
    setFavicon(href) {
        let link = document.querySelector("link[rel*='icon']");
        if (!link) {
            link = document.createElement('link');
            link.rel = 'icon';
            document.head.appendChild(link);
        }
        link.href = href;
    }
};

/**
 * Global function for updating desktop badge from anywhere.
 * @param {number} count - Total unread message count
 */
window.updateDesktopBadge = function(count) {
    // Ensure BadgeUtils is initialized before using
    if (typeof BadgeUtils !== 'undefined') {
        if (!BadgeUtils.initialized) {
            BadgeUtils.init();
        }
        BadgeUtils.updateBadge(count);
    }
};

// Auto-initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    BadgeUtils.init();
});
