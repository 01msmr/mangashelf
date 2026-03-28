// attachNumpad(inputEl, toggleBtnEl?, options?)
// options: { decimal: true }   — comma key left of 0
// options: { keepFocus: true } — re-focus input if nothing else takes focus (login screens)
function attachNumpad(inputEl, toggleBtnEl, options = {}) {

    const numpad = document.createElement('div');
    numpad.style.cssText = 'display:none;flex-direction:column;gap:6px;position:fixed;z-index:9100;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:6px;box-shadow:0 4px 20px rgba(0,0,0,0.5)';

    const bottomLeft = options.decimal ? ',' : '';
    [['1','2','3'],['4','5','6'],['7','8','9'],[bottomLeft,'0','⌫']].forEach(row => {
        const rowEl = document.createElement('div');
        rowEl.style.cssText = 'display:flex;gap:6px;justify-content:center';
        row.forEach(k => {
            if (k === '') { const sp = document.createElement('div'); sp.style.cssText='flex:1'; rowEl.appendChild(sp); return; }
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = k;
            btn.style.cssText = 'flex:1;aspect-ratio:1;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:20px;font-weight:600;cursor:pointer;-webkit-tap-highlight-color:transparent;filter:brightness(1.3)';
            btn.addEventListener('pointerdown', e => {
                e.preventDefault();
                if (k === '⌫') {
                    inputEl.value = inputEl.value.slice(0, -1);
                } else if (!inputEl.maxLength || inputEl.value.length < inputEl.maxLength) {
                    inputEl.value += k;
                }
                inputEl.dispatchEvent(new Event('input'));
            });
            rowEl.appendChild(btn);
        });
        numpad.appendChild(rowEl);
    });

    document.body.appendChild(numpad);

    function positionNumpad() {
        const rect = inputEl.getBoundingClientRect();
        const padW = Math.max(rect.width, 180);
        numpad.style.width = padW + 'px';
        const spaceBelow = window.innerHeight - rect.bottom;
        if (spaceBelow >= 200 || spaceBelow > rect.top) {
            numpad.style.top  = (rect.bottom + 4) + 'px';
            numpad.style.bottom = '';
        } else {
            numpad.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
            numpad.style.top = '';
        }
        numpad.style.left = rect.left + 'px';
    }

    function show() { positionNumpad(); numpad.style.display = 'flex'; }
    function hide() { numpad.style.display = 'none'; }

    // Always auto-show on focus — needed for inputmode="none" inputs on all devices
    inputEl.addEventListener('focus', show);
    inputEl.addEventListener('blur', () => {
        setTimeout(() => {
            const a = document.activeElement;
            // keepFocus: re-engage if nothing took focus (login/PIN screens)
            if (options.keepFocus && (!a || a === document.body)) {
                inputEl.focus();
            } else {
                hide();
            }
        }, 200);
    });

    if (toggleBtnEl) {
        toggleBtnEl.addEventListener('pointerdown', e => {
            // Prevent blur from firing on the input when toggle is tapped
            e.preventDefault();
        });
        toggleBtnEl.addEventListener('click', () => {
            const visible = numpad.style.display === 'flex';
            if (visible) { hide(); inputEl.blur(); } else { show(); inputEl.focus(); }
        });
    }
}
