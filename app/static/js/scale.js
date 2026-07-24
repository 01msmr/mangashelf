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

// Double-tap on empty background toggles fullscreen.
document.addEventListener('dblclick', function (e) {
    if (e.target.closest('button, a, input, select, textarea, [role="button"], #logo-tap-target')) return;
    if (document.fullscreenElement) {
        document.exitFullscreen();
    } else {
        document.documentElement.requestFullscreen().catch(function () {});
    }
});

// Drag-to-scroll. This kiosk's Firefox reports the touchscreen as a mouse, so
// a finger drag selects text instead of panning. Drive the nearest scrollable
// ancestor from pointer movement — works for both real touch and mouse.
(function () {
    var el = null, lastY = 0, startY = 0, moved = false, THRESH = 6;

    function scrollable(n) {
        for (; n && n.nodeType === 1; n = n.parentElement) {
            if (n.scrollHeight > n.clientHeight + 1) {
                var oy = getComputedStyle(n).overflowY;
                if (oy === 'auto' || oy === 'scroll') return n;
            }
        }
        return document.scrollingElement || document.documentElement;
    }

    document.addEventListener('pointerdown', function (e) {
        if (e.button && e.button !== 0) return;
        if (e.target.closest('input, textarea, select, [contenteditable], .rs-track, .rs-puck, .ui-scale-range, .pinpad, .pinpad-grid')) { el = null; return; }
        el = scrollable(e.target);
        startY = lastY = e.clientY;
        moved = false;
    });

    document.addEventListener('pointermove', function (e) {
        if (!el) return;
        if (!moved && Math.abs(e.clientY - startY) < THRESH) return;
        moved = true;
        el.scrollTop -= (e.clientY - lastY);
        lastY = e.clientY;
        var sel = window.getSelection && window.getSelection();
        if (sel) sel.removeAllRanges();
        e.preventDefault();
    });

    function end() { el = null; }
    document.addEventListener('pointerup', end);
    document.addEventListener('pointercancel', end);

    // Swallow the click that ends a real drag so cards/buttons don't fire.
    document.addEventListener('click', function (e) {
        if (moved) { e.stopPropagation(); e.preventDefault(); moved = false; }
    }, true);
    document.addEventListener('selectstart', function (e) {
        if (el && moved) e.preventDefault();
    });
})();
