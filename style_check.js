/**
 * style_check.js — Puppeteer visual style auditor for MangaStore
 *
 * Usage:
 *   node style_check.js [--host https://localhost:5001] [--screenshots]
 *
 * What it checks on each page:
 *   - Elements wider than the viewport (horizontal overflow)
 *   - Text smaller than MIN_FONT_PX
 *   - Buttons / inputs too small to tap (< MIN_TOUCH_PX tall)
 *   - Optionally saves a screenshot per page
 *
 * Pages are loaded as the "kiosk" viewport (800×480) and then again
 * as a mobile viewport (390×844) so both layouts are tested.
 *
 * Prerequisites:
 *   npm install puppeteer
 *   Run the Flask app first (python run.py), then run this script.
 */

const puppeteer = require('puppeteer');
const fs        = require('fs');
const path      = require('path');

// ── Config ──────────────────────────────────────────────────────────────────

const BASE_URL     = process.argv.includes('--host')
    ? process.argv[process.argv.indexOf('--host') + 1]
    : 'https://localhost:5001';

const SCREENSHOTS  = process.argv.includes('--screenshots');
const SHOTS_DIR    = path.join(__dirname, 'style_screenshots');
const MIN_FONT_PX  = 12;   // warn if rendered font-size < this
const MIN_TOUCH_PX = 36;   // warn if interactive element height < this

// Pages to audit.  auth_pages are visited without login; app_pages require login.
const AUTH_CREDS   = { username: 'admin', pin: '1489' };

const PAGES = [
    // path, label, loginRequired
    { path: '/login',           label: 'Login',          login: false },
    { path: '/scan',            label: 'Scan',           login: true  },
    { path: '/account',        label: 'Account',        login: true  },
    { path: '/books',           label: 'Book list',      login: true  },
    { path: '/phone-scan',      label: 'Phone scan',     login: true  },
];

const VIEWPORTS = [
    { name: 'kiosk',  width: 800,  height: 480  },
    { name: 'mobile', width: 390,  height: 844  },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

async function login(page) {
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' });
    // If already logged in, server redirects away from /login immediately
    if (!page.url().includes('/login')) return;
    // PIN input is set readonly by pin.js — bypass by setting value via JS
    await page.evaluate((creds) => {
        document.querySelector('input[name="username"]').value = creds.username;
        const pinEl = document.querySelector('input[name="pin"]');
        pinEl.removeAttribute('readonly');
        pinEl.value = creds.pin;
    }, AUTH_CREDS);
    await page.click('button[type="submit"]');
    // Wait up to 5s for navigation; if it stays on /login, credentials were wrong
    try {
        await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 5000 });
    } catch (_) {}
    if (page.url().includes('/login')) {
        console.error('\n  ✗ Login failed — check AUTH_CREDS in style_check.js');
        process.exit(1);
    }
}

/** Returns a list of style issues found on the current page. */
async function auditPage(page, viewportWidth) {
    return page.evaluate((minFont, minTouch, vpWidth) => {
        const issues = [];

        // 1. Elements wider than viewport → horizontal overflow
        document.querySelectorAll('*').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.right > vpWidth + 2) {   // 2px tolerance for sub-pixel
                issues.push({
                    type: 'overflow',
                    tag:  el.tagName.toLowerCase() + (el.className ? '.' + [...el.classList].join('.') : ''),
                    detail: `right edge at ${Math.round(r.right)}px (viewport ${vpWidth}px)`,
                });
            }
        });

        // 2. Text too small
        document.querySelectorAll('p, span, div, a, label, button, li, td, th, h1, h2, h3').forEach(el => {
            if (!el.offsetParent && el.tagName !== 'BODY') return;  // hidden
            const fs = parseFloat(window.getComputedStyle(el).fontSize);
            if (fs > 0 && fs < minFont && el.innerText && el.innerText.trim().length > 0) {
                issues.push({
                    type: 'small-text',
                    tag: el.tagName.toLowerCase() + (el.className ? '.' + [...el.classList].join('.') : ''),
                    detail: `font-size ${fs.toFixed(1)}px (min ${minFont}px): "${el.innerText.trim().slice(0, 50)}"`,
                });
            }
        });

        // 3. Interactive elements too small to tap
        document.querySelectorAll('button, a, input[type="submit"], input[type="button"]').forEach(el => {
            if (!el.offsetParent) return;
            const r = el.getBoundingClientRect();
            if (r.height > 0 && r.height < minTouch) {
                issues.push({
                    type: 'small-touch',
                    tag: el.tagName.toLowerCase() + (el.className ? '.' + [...el.classList].join('.') : ''),
                    detail: `height ${Math.round(r.height)}px (min ${minTouch}px): "${(el.innerText || el.value || '').trim().slice(0, 40)}"`,
                });
            }
        });

        return issues;
    }, MIN_FONT_PX, MIN_TOUCH_PX, viewportWidth);
}

// ── Main ─────────────────────────────────────────────────────────────────────

(async () => {
    if (SCREENSHOTS && !fs.existsSync(SHOTS_DIR)) fs.mkdirSync(SHOTS_DIR);

    const browser = await puppeteer.launch({
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--ignore-certificate-errors',   // allow self-signed cert
        ],
    });

    let totalIssues = 0;
    let loggedIn    = false;

    for (const vp of VIEWPORTS) {
        console.log(`\n${'═'.repeat(60)}`);
        console.log(`  VIEWPORT: ${vp.name} (${vp.width}×${vp.height})`);
        console.log(`${'═'.repeat(60)}`);

        const page = await browser.newPage();
        await page.setViewport({ width: vp.width, height: vp.height });
        loggedIn = false;

        for (const pg of PAGES) {
            // Login if needed
            if (pg.login && !loggedIn) {
                await page.setViewport({ width: vp.width, height: vp.height });
                await login(page);
                loggedIn = true;
            }

            const url = `${BASE_URL}${pg.path}`;
            try {
                await page.goto(url, { waitUntil: 'networkidle0', timeout: 10000 });
            } catch (e) {
                console.log(`  [${pg.label}] ⚠ Could not load: ${e.message}`);
                continue;
            }

            // For the account page, we need to pass the PIN gate
            if (pg.path === '/account') {
                const pinInput = await page.$('input[name="pin"]');
                if (pinInput) {
                    // PIN input may be readonly — set via JS and submit form directly
                    await page.evaluate((pin) => {
                        const el = document.querySelector('input[name="pin"]');
                        if (el) { el.removeAttribute('readonly'); el.value = pin; }
                        const form = el && el.closest('form');
                        if (form) form.submit();
                    }, AUTH_CREDS.pin);
                    await page.waitForNavigation({ waitUntil: 'networkidle0', timeout: 5000 }).catch(() => {});
                }
            }

            const issues = await auditPage(page, vp.width);

            if (SCREENSHOTS) {
                const fname = `${vp.name}_${pg.label.replace(/\s+/g, '_')}.png`;
                await page.screenshot({ path: path.join(SHOTS_DIR, fname), fullPage: false });
            }

            // Deduplicate by type+tag
            const seen    = new Set();
            const unique  = issues.filter(i => {
                const key = `${i.type}|${i.tag}`;
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
            });

            const icon = unique.length === 0 ? '✓' : '✗';
            console.log(`\n  ${icon} ${pg.label} (${url})`);
            if (unique.length === 0) {
                console.log('    No issues found.');
            } else {
                unique.forEach(i => {
                    totalIssues++;
                    const prefix = i.type === 'overflow'   ? '  [OVERFLOW]   '
                                 : i.type === 'small-text' ? '  [SMALL-TEXT] '
                                 :                           '  [SMALL-TAP]  ';
                    console.log(`    ${prefix} ${i.tag}`);
                    console.log(`               ${i.detail}`);
                });
            }
        }

        await page.close();
    }

    await browser.close();

    console.log(`\n${'═'.repeat(60)}`);
    if (totalIssues === 0) {
        console.log('  All checks passed — no style issues detected.');
    } else {
        console.log(`  Total issues found: ${totalIssues}`);
    }
    console.log(`${'═'.repeat(60)}\n`);

    process.exit(totalIssues > 0 ? 1 : 0);
})();
