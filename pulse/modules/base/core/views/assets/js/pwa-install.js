/**
 * PWA Install Helper
 *
 * Browser detection, install status, and native prompt handling for PWA installation.
 * Exposes window.PWAInstall API for use in install page and other components.
 */

(function() {
    'use strict';

    // Store the beforeinstallprompt event for later use
    let deferredPrompt = null;
    let installOutcome = null;

    // Browser detection
    function getBrowser() {
        const ua = navigator.userAgent;

        // Order matters - check more specific browsers first
        if (ua.includes('Edg/') || ua.includes('Edge/')) {
            return 'edge';
        }
        if (ua.includes('Firefox/')) {
            return 'firefox';
        }
        if (ua.includes('Chrome/') && !ua.includes('Edg/')) {
            return 'chrome';
        }
        if (ua.includes('Safari/') && !ua.includes('Chrome/')) {
            return 'safari';
        }
        return 'other';
    }

    // Platform detection
    function getPlatform() {
        const ua = navigator.userAgent;
        const platform = navigator.platform || '';

        // iOS detection (iPhone, iPad, iPod)
        if (/iPad|iPhone|iPod/.test(ua) || (platform === 'MacIntel' && navigator.maxTouchPoints > 1)) {
            return 'ios';
        }

        // Android detection
        if (/Android/.test(ua)) {
            return 'android';
        }

        // macOS detection
        if (platform.startsWith('Mac')) {
            return 'macos';
        }

        // Windows detection
        if (platform.startsWith('Win')) {
            return 'windows';
        }

        // Linux detection
        if (platform.startsWith('Linux')) {
            return 'linux';
        }

        return 'other';
    }

    // Check if app is already installed (running as PWA)
    function isInstalled() {
        // Check display-mode media query (works for most browsers)
        if (window.matchMedia('(display-mode: standalone)').matches) {
            return true;
        }

        // Check display-mode: fullscreen (some PWAs use this)
        if (window.matchMedia('(display-mode: fullscreen)').matches) {
            return true;
        }

        // Check iOS Safari standalone mode
        if (navigator.standalone === true) {
            return true;
        }

        // Check if running in TWA (Trusted Web Activity)
        if (document.referrer.includes('android-app://')) {
            return true;
        }

        return false;
    }

    // Check if we have a native install prompt available
    function hasNativePrompt() {
        return deferredPrompt !== null;
    }

    // Trigger the native install prompt (Chrome/Edge only)
    async function triggerInstall() {
        if (!deferredPrompt) {
            window.SPARQ_DEBUG && console.log('PWAInstall: No deferred prompt available');
            return { outcome: 'unavailable', error: 'No install prompt available' };
        }

        try {
            // Show the install prompt
            deferredPrompt.prompt();

            // Wait for the user's choice
            const { outcome } = await deferredPrompt.userChoice;
            installOutcome = outcome;

            // Clear the prompt - it can only be used once
            deferredPrompt = null;

            // Dispatch event for UI updates
            window.dispatchEvent(new CustomEvent('pwa-install-complete', {
                detail: { outcome }
            }));

            if (outcome === 'accepted') {
                window.dispatchEvent(new CustomEvent('pwa-installed'));
            }

            return { outcome };
        } catch (error) {
            console.error('PWAInstall: Error triggering install:', error);
            return { outcome: 'error', error: error.message };
        }
    }

    // Get browser-specific installation instructions
    function getInstructions() {
        const browser = getBrowser();
        const platform = getPlatform();

        const instructions = {
            browser,
            platform,
            supportsNativeInstall: hasNativePrompt(),
            steps: []
        };

        // Chrome on desktop
        if (browser === 'chrome' && (platform === 'windows' || platform === 'macos' || platform === 'linux')) {
            instructions.steps = [
                { icon: 'fa-plus-square', text: 'Click the install icon in the address bar (right side)' },
                { icon: 'fa-mouse-pointer', text: 'Click "Install" in the popup dialog' },
                { icon: 'fa-rocket', text: 'sparQ will open in its own window' }
            ];
            instructions.note = 'You can also use the menu (⋮) → "Install sparQ..."';
            return instructions;
        }

        // Chrome on Android
        if (browser === 'chrome' && platform === 'android') {
            instructions.steps = [
                { icon: 'fa-ellipsis-v', text: 'Tap the menu button (⋮) in the top right' },
                { icon: 'fa-plus-square', text: 'Tap "Install app" or "Add to Home screen"' },
                { icon: 'fa-check', text: 'Tap "Install" to confirm' }
            ];
            return instructions;
        }

        // Edge on desktop
        if (browser === 'edge' && (platform === 'windows' || platform === 'macos' || platform === 'linux')) {
            instructions.steps = [
                { icon: 'fa-plus-square', text: 'Click the install icon in the address bar' },
                { icon: 'fa-mouse-pointer', text: 'Click "Install" in the popup' },
                { icon: 'fa-rocket', text: 'sparQ will be added to your apps' }
            ];
            instructions.note = 'You can also use the menu (⋯) → Apps → "Install sparQ"';
            return instructions;
        }

        // Safari on iOS
        if (browser === 'safari' && platform === 'ios') {
            instructions.steps = [
                { icon: 'fa-share-square', text: 'Tap the Share button at the bottom of the screen' },
                { icon: 'fa-plus-square', text: 'Scroll down and tap "Add to Home Screen"' },
                { icon: 'fa-edit', text: 'Optionally customize the name, then tap "Add"' }
            ];
            instructions.note = 'The share button looks like a square with an arrow pointing up';
            return instructions;
        }

        // Safari on macOS (17+)
        if (browser === 'safari' && platform === 'macos') {
            instructions.steps = [
                { icon: 'fa-bars', text: 'Click "File" in the menu bar' },
                { icon: 'fa-plus-square', text: 'Click "Add to Dock..."' },
                { icon: 'fa-check', text: 'Confirm to add sparQ to your Dock' }
            ];
            instructions.note = 'Requires macOS Sonoma (14) or later';
            return instructions;
        }

        // Firefox (not supported)
        if (browser === 'firefox') {
            instructions.steps = [];
            instructions.unsupported = true;
            instructions.unsupportedMessage = 'Firefox does not support PWA installation on desktop. For the best experience, please use Chrome, Edge, or Safari.';
            instructions.alternatives = [
                { name: 'Google Chrome', url: 'https://www.google.com/chrome/', icon: 'fa-brands fa-chrome' },
                { name: 'Microsoft Edge', url: 'https://www.microsoft.com/edge', icon: 'fa-brands fa-edge' },
                { name: 'Safari', url: 'https://www.apple.com/safari/', icon: 'fa-brands fa-safari' }
            ];
            return instructions;
        }

        // Default/unknown browser
        instructions.steps = [
            { icon: 'fa-question-circle', text: 'Look for an "Install" or "Add to Home Screen" option' },
            { icon: 'fa-bars', text: 'Check the browser menu or address bar' }
        ];
        instructions.note = 'For best results, use Chrome, Edge, or Safari';
        return instructions;
    }

    // Listen for the beforeinstallprompt event
    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent the mini-infobar from appearing on mobile
        e.preventDefault();

        // Store the event for later use
        deferredPrompt = e;

        // Dispatch custom event so UI can update
        window.dispatchEvent(new CustomEvent('pwa-install-available'));

        window.SPARQ_DEBUG && console.log('PWAInstall: Install prompt captured and ready');
    });

    // Listen for successful installation
    window.addEventListener('appinstalled', () => {
        // Clear the deferred prompt
        deferredPrompt = null;

        // Dispatch custom event
        window.dispatchEvent(new CustomEvent('pwa-installed'));

        window.SPARQ_DEBUG && console.log('PWAInstall: App was installed');
    });

    // Expose public API
    window.PWAInstall = {
        getBrowser,
        getPlatform,
        isInstalled,
        hasNativePrompt,
        triggerInstall,
        getInstructions,

        // Helper to get a friendly browser name
        getBrowserName() {
            const names = {
                chrome: 'Google Chrome',
                edge: 'Microsoft Edge',
                safari: 'Safari',
                firefox: 'Firefox',
                other: 'your browser'
            };
            return names[getBrowser()] || 'your browser';
        },

        // Helper to get a friendly platform name
        getPlatformName() {
            const names = {
                ios: 'iOS',
                android: 'Android',
                macos: 'macOS',
                windows: 'Windows',
                linux: 'Linux',
                other: 'your device'
            };
            return names[getPlatform()] || 'your device';
        }
    };

    // Log initial state for debugging
    window.SPARQ_DEBUG && console.log('PWAInstall initialized:', {
        browser: getBrowser(),
        platform: getPlatform(),
        isInstalled: isInstalled()
    });

})();
