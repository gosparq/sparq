/**
 * Notification Sound
 *
 * Generates a Slack-like "knock brush" notification sound using Web Audio API.
 * No external audio files required.
 */

(function() {
    'use strict';

    var audioContext = null;
    var isEnabled = true;

    // Get or create AudioContext (lazy initialization)
    function getAudioContext() {
        if (!audioContext) {
            var AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                audioContext = new AudioContext();
            }
        }
        return audioContext;
    }

    // Resume audio context if suspended (required after user interaction)
    function ensureAudioContextResumed() {
        var ctx = getAudioContext();
        if (ctx && ctx.state === 'suspended') {
            ctx.resume();
        }
        return ctx;
    }

    /**
     * Play the knock/pop notification sound.
     * Mimics Slack's wooden "knock brush" sound.
     */
    function playKnock() {
        if (!isEnabled) return;

        var ctx = ensureAudioContextResumed();
        if (!ctx) return;

        var now = ctx.currentTime;

        // Create two quick "knock" tones for the brush effect
        playTone(ctx, now, 800, 0.08, 0.15);        // First knock (higher)
        playTone(ctx, now + 0.08, 600, 0.06, 0.12); // Second knock (lower, softer)
    }

    /**
     * Play a single knock tone.
     */
    function playTone(ctx, startTime, frequency, duration, volume) {
        // Oscillator for the tone
        var osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(frequency, startTime);
        osc.frequency.exponentialRampToValueAtTime(frequency * 0.5, startTime + duration);

        // Gain envelope for quick attack and decay
        var gainNode = ctx.createGain();
        gainNode.gain.setValueAtTime(0, startTime);
        gainNode.gain.linearRampToValueAtTime(volume, startTime + 0.005); // Quick attack
        gainNode.gain.exponentialRampToValueAtTime(0.001, startTime + duration); // Decay

        // Add a subtle filter for warmth
        var filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(2000, startTime);

        // Connect: oscillator -> filter -> gain -> output
        osc.connect(filter);
        filter.connect(gainNode);
        gainNode.connect(ctx.destination);

        // Play
        osc.start(startTime);
        osc.stop(startTime + duration + 0.05);
    }

    /**
     * Play a softer "pop" sound (alternative).
     */
    function playPop() {
        if (!isEnabled) return;

        var ctx = ensureAudioContextResumed();
        if (!ctx) return;

        var now = ctx.currentTime;

        var osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.exponentialRampToValueAtTime(220, now + 0.1);

        var gainNode = ctx.createGain();
        gainNode.gain.setValueAtTime(0.2, now);
        gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.1);

        osc.connect(gainNode);
        gainNode.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + 0.15);
    }

    /**
     * Enable/disable notification sounds.
     */
    function setEnabled(enabled) {
        isEnabled = enabled;
        // Store preference
        try {
            localStorage.setItem('sparq_notification_sound', enabled ? '1' : '0');
        } catch (e) {}
    }

    /**
     * Check if sounds are enabled.
     */
    function getEnabled() {
        try {
            var stored = localStorage.getItem('sparq_notification_sound');
            if (stored !== null) {
                return stored === '1';
            }
        } catch (e) {}
        return true; // Default enabled
    }

    // Initialize from stored preference
    isEnabled = getEnabled();

    // Expose public API
    window.NotificationSound = {
        playKnock: playKnock,
        playPop: playPop,
        play: playKnock, // Default sound
        setEnabled: setEnabled,
        isEnabled: function() { return isEnabled; }
    };

})();
