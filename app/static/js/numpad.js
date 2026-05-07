// attachNumpad(inputEl, toggleBtnEl?, options?)
// options: { decimal: true }   — comma key left of 0
// options: { keepFocus: true } — re-focus input if nothing else takes focus (login screens)
function attachNumpad(inputEl, toggleBtnEl, options = {}) {

    const numpad = document.createElement('div');
    numpad.style.cssText = 'display:none;flex-direction:column;gap:8px;position:fixed;z-index:9100;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:10px;box-shadow:0 4px 24px rgba(0,0,0,0.55)';

    const bottomLeft = options.decimal ? ',' : '';
    [['1','2','3'],['4','5','6'],['7','8','9'],[bottomLeft,'0','⌫']].forEach(row => {
        const rowEl = document.createElement('div');
        rowEl.style.cssText = 'display:flex;gap:8px;justify-content:center';
        row.forEach(k => {
            if (k === '') { const sp = document.createElement('div'); sp.style.cssText='flex:1'; rowEl.appendChild(sp); return; }
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = k;
            btn.style.cssText = 'flex:1;min-width:60px;aspect-ratio:1;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:24px;font-weight:600;cursor:pointer;-webkit-tap-highlight-color:transparent;filter:brightness(1.3)';
            btn.addEventListener('pointerdown', e => {
                e.preventDefault();
                if (k === '⌫') {
                    inputEl.value = inputEl.value.slice(0, -1);
                } else if (inputEl.maxLength < 0 || inputEl.value.length < inputEl.maxLength) {
                    inputEl.value += k;
                }
                inputEl.dispatchEvent(new Event('input'));
            });
            rowEl.appendChild(btn);
        });
        numpad.appendChild(rowEl);
    });

    document.body.appendChild(numpad);

    function show() {
        numpad.style.display = 'flex';
        numpad.style.left = '-9999px';

        const rect = inputEl.getBoundingClientRect();
        const padW = Math.max(rect.width, 240);
        numpad.style.width = padW + 'px';
        const padH = numpad.offsetHeight;

        let left = rect.left;
        left = Math.min(left, window.innerWidth  - padW - 8);
        left = Math.max(left, 8);
        numpad.style.left = left + 'px';

        let top = rect.bottom + 6;
        if (top + padH > window.innerHeight - 8) top = rect.top - padH - 6;
        top = Math.max(top, 8);
        numpad.style.top    = top + 'px';
        numpad.style.bottom = '';
    }

    function hide() { numpad.style.display = 'none'; }

    // Always auto-show on focus — needed for inputmode="none" inputs on all devices
    inputEl.addEventListener('focus', show);
    inputEl.addEventListener('blur', () => {
        setTimeout(() => {
            const a = document.activeElement;
            if (options.keepFocus && (!a || a === document.body)) {
                inputEl.focus();
            } else {
                hide();
            }
        }, 200);
    });

    if (toggleBtnEl) {
        toggleBtnEl.addEventListener('pointerdown', e => {
            e.preventDefault();
        });
        toggleBtnEl.addEventListener('click', () => {
            const visible = numpad.style.display === 'flex';
            if (visible) { hide(); inputEl.blur(); } else { show(); inputEl.focus(); }
        });
    }

    // Close numpad immediately on any tap outside the numpad / input / toggle
    document.addEventListener('pointerdown', function outsideHandler(e) {
        if (numpad.style.display !== 'flex') return;
        if (numpad.contains(e.target)) return;
        if (e.target === inputEl) return;
        if (toggleBtnEl && toggleBtnEl.contains(e.target)) return;
        hide();
    }, { capture: true });
}
