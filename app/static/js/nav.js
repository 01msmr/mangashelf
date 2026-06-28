/**
 * Renders the site header once the current user is loaded.
 * Call renderNav(user) after fetching /api/auth/me.
 */
function renderNav(user) {
    const header = document.getElementById('site-header');
    if (!header) return;

    const balanceClass = user.guthaben >= 5 ? 'bal-ok' : user.guthaben > 0 ? 'bal-warn' : 'bal-danger';
    const path         = window.location.pathname;
    const onAccount    = path === '/account.html';
    const onIndex      = path === '/index.html' || path === '/';
    const onAdmin      = path.startsWith('/admin/');
    // The gold "Admin" badge IS the link to the admin section (no separate button).
    const adminTip     = (typeof Lang !== 'undefined' && Lang.t) ? Lang.t('nav.admin') : 'Admin';
    const adminBadge   = user.is_admin
        ? `<a href="/admin/users.html" class="badge-admin-link${onAdmin ? ' nav-active' : ''}" data-tip="${esc(adminTip)}"><span class="badge-admin">Admin</span></a>`
        : '';

    header.innerHTML = `
        <div class="header-left-group">
            <a href="/account.html" class="btn btn-ghost btn-sm user-badge${onAccount ? ' nav-active' : ''}">${esc(user.username)}</a>${adminBadge}<span class="header-balance ${balanceClass}">${fmtEur(user.guthaben)}</span>
        </div>
        <div class="header-center">
            <a href="/index.html" class="app-logo${onIndex ? ' nav-active' : ''}"><span class="logo-badge"><img src="/static/img/kinoko.svg"></span>Manga<span class="logo-shelf">${(typeof Lang !== 'undefined' && Lang.t) ? Lang.t('logo.shelf') : 'Shelf'}</span></a>
            ${_langDropdownHtml()}
        </div>
        <div class="header-right">
            <button class="btn btn-ghost btn-sm" id="nav-logout"><i class="fa-solid fa-right-from-bracket"></i> ${(typeof Lang !== 'undefined' && Lang.t) ? Lang.t('nav.logout') : 'Logout'}</button>
        </div>
    `;

    document.getElementById('nav-logout').addEventListener('click', async () => {
        await API.post('/api/auth/logout');
        window.location.href = '/login.html';
    });
    _wireLangDropdown();
}

/* ── Language flag dropdown (next to the title) ───────────────────────────── */
const _FLAGS = {
    en: `<svg class="lang-flag" viewBox="0 0 60 30" preserveAspectRatio="none" aria-hidden="true"><rect width="60" height="30" fill="#012169"/><path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/><path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" stroke-width="3"/><path d="M30,0 V30 M0,15 H60" stroke="#fff" stroke-width="10"/><path d="M30,0 V30 M0,15 H60" stroke="#C8102E" stroke-width="6"/></svg>`,
    de: `<svg class="lang-flag" viewBox="0 0 5 3" preserveAspectRatio="none" aria-hidden="true"><rect width="5" height="3" fill="#FFCE00"/><rect width="5" height="2" fill="#DD0000"/><rect width="5" height="1" fill="#000"/></svg>`,
    schwaebisch: `<svg class="lang-flag" viewBox="0 0 5 3" preserveAspectRatio="none" aria-hidden="true"><rect width="5" height="3" fill="#FFCE00"/><rect width="5" height="1.5" fill="#000"/></svg>`,
};
const _LANG_LABELS = { en: 'EN', de: 'DE', schwaebisch: 'Schwob' };
const _LANG_ORDER  = ['en', 'de', 'schwaebisch'];

function _langDropdownHtml() {
    const cur = (typeof Lang !== 'undefined') ? Lang.current : 'de';
    // Flags only in the list (no labels, no tooltip).
    const opts = _LANG_ORDER.map(c =>
        `<button type="button" class="lang-option${c === cur ? ' active' : ''}" data-lang="${c}">${_FLAGS[c]}</button>`).join('');
    return `<div class="lang-dropdown" id="lang-dropdown">
            <button type="button" class="lang-current" id="lang-toggle">${_FLAGS[cur] || ''}<span class="lang-code">${_LANG_LABELS[cur] || ''}</span></button>
            <div class="lang-menu" id="lang-menu">${opts}</div>
        </div>`;
}

function _wireLangDropdown() {
    const dd = document.getElementById('lang-dropdown');
    if (!dd) return;
    const menu = document.getElementById('lang-menu');
    document.getElementById('lang-toggle').addEventListener('click', e => {
        e.stopPropagation();
        menu.classList.toggle('open');
    });
    document.addEventListener('click', e => { if (!dd.contains(e.target)) menu.classList.remove('open'); });
    menu.querySelectorAll('.lang-option').forEach(btn => {
        btn.addEventListener('click', async () => {
            const code = btn.dataset.lang;
            menu.classList.remove('open');
            if (code === Lang.current) return;
            Lang.set(code);
            await API.post(`/api/account/language/${code}`).catch(() => {});
            window.location.reload();
        });
    });
}

function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/**
 * Populate the overdue-count notification badge on the admin nav. Runs on every
 * admin page (the badge element exists in each admin page's nav) so the count
 * is always visible, not only on the overdue panel.
 */
async function loadOverdueBadge() {
    const badge = document.getElementById('overdue-badge');
    if (!badge) return;
    try {
        const items = await API.get('/api/admin/overdue');
        const n = items.length;
        badge.textContent = n;
        badge.style.display = n > 0 ? 'inline-block' : 'none';
    } catch (_) { /* not verified / not allowed → leave hidden */ }
}

/**
 * Load current user, render nav, start idle timer, return user object.
 * Redirects to login on 401.
 */
async function initPage() {
    try {
        const user = await API.get('/api/auth/me');
        renderNav(user);
        startIdleTimer();
        if (user.is_admin) loadOverdueBadge();
        return user;
    } catch (err) {
        if (err.status === 401) {
            window.location.href = '/login.html';
        }
        throw err;
    }
}

/* ── Auto-logout after 90 s of inactivity ─────────────────────────────────── */
let _idleTimer = null;
const IDLE_MS = 90_000;

function startIdleTimer() {
    function reset() {
        clearTimeout(_idleTimer);
        _idleTimer = setTimeout(async () => {
            await API.post('/api/auth/logout').catch(() => {});
            window.location.href = '/login.html';
        }, IDLE_MS);
    }
    ['click', 'keydown', 'touchstart', 'mousemove'].forEach(ev =>
        document.addEventListener(ev, reset, { passive: true }));
    reset();
}

/* ── JS tooltip ───────────────────────────────────────────────────────────── */

(function () {
    let tip = null;

    function getTip() {
        if (!tip) {
            tip = document.createElement('div');
            tip.id = 'js-tooltip';
            document.body.appendChild(tip);
        }
        return tip;
    }

    document.addEventListener('mouseover', function (e) {
        const el = e.target.closest('[data-tip]');
        if (!el) return;
        const t = getTip();
        t.textContent = el.dataset.tip;
        t.style.display = 'block';
        // Position after display so offsetWidth is known
        const r = el.getBoundingClientRect();
        const tw = t.offsetWidth, th = t.offsetHeight;
        // Clamp into the viewport so long tooltips never run off-screen.
        let left = r.right - tw;
        left = Math.max(6, Math.min(left, window.innerWidth - tw - 6));
        let top = r.bottom + 6;
        if (top + th > window.innerHeight - 6) top = r.top - th - 6;  // flip above
        t.style.top  = top + 'px';
        t.style.left = left + 'px';
    });

    document.addEventListener('mouseout', function (e) {
        const el = e.target.closest('[data-tip]');
        if (!el) return;
        const t = getTip();
        t.style.display = 'none';
    });
})();

/* ── Admin section PIN gate ───────────────────────────────────────────────── */

/**
 * Call this at the start of every admin page init.
 * Checks if the admin PIN was recently entered; if not, shows a PIN prompt.
 * onVerified() is called once the user is cleared.
 */
async function requireAdminPin(onVerified) {
    // Cover the page immediately so the admin content never flashes before the
    // verification / PIN gate resolves (no background flicker on entry).
    const overlay = document.createElement('div');
    overlay.id = 'admin-pin-overlay';
    overlay.className = 'overlay-admin';
    document.body.appendChild(overlay);
    try {
        await API.get('/api/admin/verified');
        overlay.remove();
        onVerified();
    } catch (err) {
        if (err.status === 403) {
            _fillAdminPinPrompt(overlay, onVerified);
        } else if (err.status === 401) {
            window.location.href = '/login.html';
        } else {
            overlay.remove();
        }
    }
}

// Fills the already-shown cover overlay with the admin PIN gate. Uses the shared
// makePinField module (8 digits = user PIN + admin PIN), keyboard support included.
function _fillAdminPinPrompt(overlay, onVerified) {
    overlay.innerHTML = `
        <div class="pin-card pin-card-wide">
            <div class="pin-card-label">${Lang.t('adminPin.title')}</div>
            <div class="pin-hint">${Lang.t('adminPin.hint')}</div>
            <div id="ap-error" class="pin-error" style="display:none"></div>
            <div id="ap-step"></div>
            <div class="pin-actions">
                <button class="btn btn-ghost" id="ap-cancel">${Lang.t('adminPin.cancel')}</button>
            </div>
        </div>`;

    const errEl = overlay.querySelector('#ap-error');
    const pf = makePinField(overlay.querySelector('#ap-step'), '', 8);

    let busy = false;
    const obs = new MutationObserver(async () => {
        if (busy || pf.getValue().length !== 8) return;
        busy = true;
        errEl.style.display = 'none';
        try {
            await API.post('/api/admin/verify', { pin: pf.getValue() });
            obs.disconnect();
            overlay.remove();
            onVerified();
        } catch (err) {
            errEl.textContent = err.detail || 'Incorrect PIN.';
            errEl.style.display = 'block';
            pf.reset();
            busy = false;
        }
    });
    obs.observe(overlay.querySelector('.pf-dots'), { subtree: true, attributes: true, attributeFilter: ['class'] });

    // Keep the cover overlay up while navigating away so the empty admin page
    // never flashes through ("leerer screen" on cancel).
    function cancel() {
        document.removeEventListener('keydown', onEsc);
        window.location.href = '/index.html';
    }
    function onEsc(e) { if (e.key === 'Escape') cancel(); }
    document.addEventListener('keydown', onEsc);
    overlay.querySelector('#ap-cancel').addEventListener('click', cancel);
}
