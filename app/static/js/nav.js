/**
 * Renders the site header once the current user is loaded.
 * Call renderNav(user) after fetching /api/auth/me.
 */
function renderNav(user) {
    const header = document.getElementById('site-header');
    if (!header) return;

    const adminBadge = user.is_admin ? '<span class="badge-admin">Admin</span>' : '';
    const adminLink  = user.is_admin ? `<a href="/admin/users.html" class="btn btn-ghost btn-sm"><i class="fa-solid fa-shield-halved"></i> admin section</a>` : '';

    header.innerHTML = `
        <a href="/account.html" class="btn btn-ghost btn-sm user-badge">${esc(user.username)}</a>${adminBadge}
        <div class="header-left">
            <a href="/index.html" class="app-logo"><span class="logo-badge"><img src="/static/img/kinoko.svg" style="width:32px;height:32px"></span>Manga<span>Shelf</span></a>
        </div>
        <div class="header-right">
            ${adminLink}
            <button class="btn btn-ghost btn-sm" id="nav-logout"><i class="fa-solid fa-right-from-bracket"></i> Logout</button>
        </div>
    `;

    document.getElementById('nav-logout').addEventListener('click', async () => {
        await API.post('/api/auth/logout');
        window.location.href = '/login.html';
    });
}

function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/**
 * Load current user, render nav, start idle timer, return user object.
 * Redirects to login on 401.
 */
async function initPage() {
    try {
        const user = await API.get('/api/auth/me');
        renderNav(user);
        startIdleTimer();
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

/* ── Admin section PIN gate ───────────────────────────────────────────────── */

/**
 * Call this at the start of every admin page init.
 * Checks if the admin PIN was recently entered; if not, shows a PIN prompt.
 * onVerified() is called once the user is cleared.
 */
async function requireAdminPin(onVerified) {
    try {
        await API.get('/api/admin/verified');
        onVerified();
    } catch (err) {
        if (err.status === 403) {
            _showAdminPinPrompt(onVerified);
        } else if (err.status === 401) {
            window.location.href = '/login.html';
        }
    }
}

function _showAdminPinPrompt(onVerified) {
    const overlay = document.createElement('div');
    overlay.id = 'admin-pin-overlay';
    overlay.style.cssText =
        'position:fixed;inset:0;background:rgba(13,13,26,.92);z-index:9000;' +
        'display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px)';
    overlay.innerHTML = `
        <div class="pin-card" style="max-width:340px;width:100%">
            <div class="pin-card-label">Admin Access</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:14px;text-align:center;letter-spacing:0.5px">
                Your PIN &nbsp;+&nbsp; Admin PIN
            </div>
            <div id="ap-error" class="pin-error"></div>
            <div id="ap-dots" style="display:flex;justify-content:center;align-items:center;gap:10px;margin-bottom:16px">
                <div id="apd-0" class="dot"></div><div id="apd-1" class="dot"></div>
                <div id="apd-2" class="dot"></div><div id="apd-3" class="dot"></div>
                <div style="width:14px;height:2px;background:var(--border);border-radius:1px;margin:0 2px"></div>
                <div id="apd-4" class="dot"></div><div id="apd-5" class="dot"></div>
                <div id="apd-6" class="dot"></div><div id="apd-7" class="dot"></div>
            </div>
            <input type="password" id="ap-input" class="pin-text-input"
                   inputmode="numeric" maxlength="8" placeholder="••••••••" autocomplete="off"
                   style="letter-spacing:10px;font-size:var(--text-base)">
            <div class="pinpad-grid">
                <button class="pinpad-key" data-ap="1">1</button>
                <button class="pinpad-key" data-ap="2">2</button>
                <button class="pinpad-key" data-ap="3">3</button>
                <button class="pinpad-key" data-ap="4">4</button>
                <button class="pinpad-key" data-ap="5">5</button>
                <button class="pinpad-key" data-ap="6">6</button>
                <button class="pinpad-key" data-ap="7">7</button>
                <button class="pinpad-key" data-ap="8">8</button>
                <button class="pinpad-key" data-ap="9">9</button>
                <button class="pinpad-key" data-ap="clear">C</button>
                <button class="pinpad-key" data-ap="0">0</button>
                <button class="pinpad-key" data-ap="back">⌫</button>
            </div>
            <div class="pin-actions">
                <button class="btn btn-ghost" id="ap-cancel">Cancel</button>
            </div>
        </div>`;
    document.body.appendChild(overlay);

    const input  = overlay.querySelector('#ap-input');
    const errEl  = overlay.querySelector('#ap-error');
    let apPin = '';

    function updateDots() {
        for (let i = 0; i < 8; i++) {
            const dot = overlay.querySelector(`#apd-${i}`);
            if (dot) dot.classList.toggle('filled', i < apPin.length);
        }
        input.value = apPin;
    }

    async function doVerify() {
        if (apPin.length !== 8) return;
        errEl.style.display = 'none';
        try {
            await API.post('/api/admin/verify', { pin: apPin });
            overlay.remove();
            onVerified();
        } catch (err) {
            errEl.textContent = err.detail || 'Incorrect PIN.';
            errEl.style.display = 'block';
            apPin = ''; updateDots();
            input.focus();
        }
    }

    overlay.querySelectorAll('.pinpad-key').forEach(btn => {
        btn.addEventListener('pointerdown', e => {
            e.preventDefault();
            const k = btn.dataset.ap;
            if (k === 'back')       { apPin = apPin.slice(0, -1); }
            else if (k === 'clear') { apPin = ''; }
            else if (apPin.length < 8) { apPin += k; }
            updateDots();
            if (apPin.length === 8) setTimeout(doVerify, 150);
        });
    });

    input.addEventListener('input', function() {
        const v = this.value.replace(/\D/g, '').slice(0, 8);
        apPin = v; updateDots();
        if (apPin.length === 8) setTimeout(doVerify, 150);
    });

    overlay.querySelector('#ap-cancel').addEventListener('click', () => {
        overlay.remove();
        window.location.href = '/index.html';
    });

    input.addEventListener('keydown', e => { if (e.key === 'Escape') { overlay.remove(); window.location.href = '/index.html'; } });
    input.focus();
}
