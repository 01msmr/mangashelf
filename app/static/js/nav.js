/**
 * Renders the site header once the current user is loaded.
 * Call renderNav(user) after fetching /api/auth/me.
 */
function renderNav(user) {
    const header = document.getElementById('site-header');
    if (!header) return;

    const adminBadge = user.is_admin ? '<span class="badge-admin">Admin</span>' : '';
    const adminLink  = user.is_admin ? `<a href="/admin/users.html" class="btn btn-ghost btn-sm">Admin</a>` : '';

    header.innerHTML = `
        <div class="header-left">
            <a href="/index.html" class="app-logo">Manga<span>Store</span></a>
        </div>
        <div class="header-right">
            <span class="user-badge">${esc(user.username)} ${adminBadge}</span>
            <a href="/account.html" class="btn btn-ghost btn-sm">Account</a>
            ${adminLink}
            <button class="btn btn-ghost btn-sm" id="nav-logout">Logout</button>
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
        'position:fixed;inset:0;background:rgba(0,0,0,0.82);z-index:9000;' +
        'display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px)';
    overlay.innerHTML = `
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;
                    padding:28px 28px 24px;width:300px;box-shadow:var(--shadow)">
            <div style="font-size:13px;font-weight:700;color:var(--text-muted);text-align:center;
                        margin-bottom:16px;text-transform:uppercase;letter-spacing:0.7px">
                Admin PIN
            </div>
            <input type="password" id="ap-input" inputmode="numeric" maxlength="4"
                   placeholder="••••" autocomplete="off"
                   style="width:100%;height:56px;background:var(--surface-2);
                          border:1px solid var(--border);border-radius:8px;
                          color:var(--text);font-size:24px;letter-spacing:12px;
                          text-align:center;outline:none;margin-bottom:10px;
                          font-family:inherit;caret-color:transparent">
            <div id="ap-error" style="display:none;background:var(--primary-dim);
                 border:1px solid var(--primary);border-radius:8px;color:var(--primary);
                 font-size:14px;font-weight:600;padding:8px 12px;text-align:center;
                 margin-bottom:10px"></div>
            <button id="ap-confirm" style="width:100%;height:48px;background:var(--primary);
                    color:#fff;border:none;border-radius:8px;font-size:16px;font-weight:700;
                    cursor:pointer">Confirm</button>
        </div>`;
    document.body.appendChild(overlay);

    const input  = overlay.querySelector('#ap-input');
    const errEl  = overlay.querySelector('#ap-error');
    const btnOk  = overlay.querySelector('#ap-confirm');
    input.focus();

    async function doVerify() {
        const pin = input.value.trim();
        errEl.style.display = 'none';
        try {
            await API.post('/api/admin/verify', { pin });
            overlay.remove();
            onVerified();
        } catch (err) {
            errEl.textContent = err.detail || 'Incorrect PIN.';
            errEl.style.display = 'block';
            input.value = '';
            input.focus();
        }
    }

    btnOk.addEventListener('click', doVerify);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') doVerify(); });
    input.addEventListener('input', () => { if (input.value.length === 4) setTimeout(doVerify, 150); });
}
