/**
 * UI scale — per-device global zoom for the kiosk.
 *
 * The whole stylesheet is sized in rem off the root <html> font-size, so
 * setting that one value scales every element uniformly. The chosen size is
 * stored in localStorage (per-device, which is right for a fixed kiosk) and
 * applied here as early as possible to avoid a flash of unscaled UI.
 *
 * Load this in <head> BEFORE the stylesheet on every page.
 */
(function () {
    var DEFAULT = 23, MIN = 16, MAX = 28;   // px; DEFAULT matches style.css root

    // localStorage can throw (private mode / disabled) — never let that break a page.
    function read()  { try { return localStorage.getItem('uiRootPx'); } catch (e) { return null; } }
    function write(v){ try { localStorage.setItem('uiRootPx', v); } catch (e) {} }
    function wipe()  { try { localStorage.removeItem('uiRootPx'); } catch (e) {} }

    function clamp(px) {
        px = parseFloat(px);
        if (!px || px < MIN || px > MAX) return null;
        return px;
    }

    var stored = clamp(read());
    if (stored) document.documentElement.style.fontSize = stored + 'px';

    window.UIScale = {
        MIN: MIN, MAX: MAX, DEFAULT: DEFAULT,
        get: function () { return clamp(read()) || DEFAULT; },
        /** Apply and persist a root size in px. Returns the clamped value used. */
        set: function (px) {
            px = Math.round(Math.min(MAX, Math.max(MIN, parseFloat(px))));
            write(px);
            document.documentElement.style.fontSize = px + 'px';
            return px;
        },
        /** Back to the stylesheet default. */
        reset: function () {
            wipe();
            document.documentElement.style.fontSize = '';
        },
        /** Percentage relative to DEFAULT, for display. */
        pct: function (px) { return Math.round((px || this.get()) / DEFAULT * 100); }
    };
})();
