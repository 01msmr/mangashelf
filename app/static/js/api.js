/**
 * Thin fetch wrapper. All requests go to the same origin.
 * Throws {status, detail} on non-2xx responses.
 */
async function api(method, path, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
    };
    if (body !== null) opts.body = JSON.stringify(body);

    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
        const err = new Error(data.detail || `HTTP ${res.status}`);
        err.status = res.status;
        err.detail = data.detail || `HTTP ${res.status}`;
        err.data   = data;
        throw err;
    }
    return data;
}

const API = {
    get:    (path)        => api('GET',    path),
    post:   (path, body)  => api('POST',   path, body),
    delete: (path)        => api('DELETE', path),
};

/** Format euro amount — omits decimals when whole number */
function fmtEur(n) {
    if (n == null) return '—';
    return (n % 1 === 0 ? Math.round(n).toString() : n.toFixed(2)) + ' €';
}

/** Format ISO date string — locale-aware, no leading zeros */
function fmtDate(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        const lang = (typeof Lang !== 'undefined') ? Lang.current : 'en';
        if (lang === 'en') {
            return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'numeric', year: 'numeric' });
        }
        // de / swb: "12. 3. 2026"
        const raw = d.toLocaleDateString('de-DE', { day: 'numeric', month: 'numeric', year: 'numeric' });
        return raw.replace(/\.(\d)/g, '. $1');
    } catch { return iso; }
}

/** Show an error message element */
function showError(el, msg) {
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
}

function hideError(el) {
    if (!el) return;
    el.textContent = '';
    el.style.display = 'none';
}

/** Redirect to login if not authenticated */
function handleAuthError(err) {
    if (err.status === 401) {
        window.location.href = '/login.html';
        return true;
    }
    return false;
}
