/**
 * PinPad — touch-friendly 4-digit PIN entry overlay.
 *
 * Usage: add data-pin attribute to any <input type="password">
 * The overlay opens on focus and handles both touch and physical keyboard.
 *
 *   <input type="password" id="my-pin" name="pin" data-pin inputmode="none">
 */

let activePinPad = null;
let padCounter   = 0;

class PinPad {
    constructor(inputEl) {
        this.input    = inputEl;
        this.padId    = ++padCounter;
        this.overlay  = null;
        this.dotsEl   = null;
        this._build();
        this._bindInput();
    }

    // ------------------------------------------------------------------ build

    _build() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'pinpad-overlay';
        this.overlay.setAttribute('aria-modal', 'true');
        this.overlay.setAttribute('role', 'dialog');

        const label = this.input.dataset.pinLabel || 'Enter PIN';

        this.overlay.innerHTML = `
            <div class="pinpad">
                <div class="pinpad-label">${label}</div>
                <div class="pinpad-dots" id="pinpad-dots-${this.padId}">
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                    <span class="dot"></span>
                </div>
                <div class="pinpad-grid">
                    <button class="pinpad-key" data-key="1" type="button">1</button>
                    <button class="pinpad-key" data-key="2" type="button">2</button>
                    <button class="pinpad-key" data-key="3" type="button">3</button>
                    <button class="pinpad-key" data-key="4" type="button">4</button>
                    <button class="pinpad-key" data-key="5" type="button">5</button>
                    <button class="pinpad-key" data-key="6" type="button">6</button>
                    <button class="pinpad-key" data-key="7" type="button">7</button>
                    <button class="pinpad-key" data-key="8" type="button">8</button>
                    <button class="pinpad-key" data-key="9" type="button">9</button>
                    <button class="pinpad-key pinpad-key-clear" data-key="clear" type="button">C</button>
                    <button class="pinpad-key" data-key="0" type="button">0</button>
                    <button class="pinpad-key pinpad-key-back" data-key="back" type="button">&#9003;</button>
                </div>
                <div class="pinpad-actions">
                    <button class="btn btn-ghost pinpad-cancel" type="button">Cancel</button>
                    <button class="btn btn-primary pinpad-confirm" type="button">Confirm</button>
                </div>
            </div>
        `;

        this.dotsEl = this.overlay.querySelector(`#pinpad-dots-${this.padId}`);

        // Number / backspace / clear key clicks
        this.overlay.querySelectorAll('.pinpad-key').forEach(btn => {
            btn.addEventListener('pointerdown', (e) => {
                e.preventDefault();
                this._handleKey(btn.dataset.key);
            });
        });

        this.overlay.querySelector('.pinpad-cancel').addEventListener('pointerdown', (e) => {
            e.preventDefault();
            this.input.value = '';
            this._updateDots();
            this._hide();
        });

        this.overlay.querySelector('.pinpad-confirm').addEventListener('pointerdown', (e) => {
            e.preventDefault();
            this._confirm();
        });

        document.body.appendChild(this.overlay);
    }

    // ---------------------------------------------------------------- input binding

    _bindInput() {
        // Prevent system keyboard on touch devices
        this.input.setAttribute('inputmode', 'none');
        this.input.setAttribute('autocomplete', 'off');
        this.input.setAttribute('readonly', 'readonly');

        this.input.addEventListener('focus', () => this._show());

        // Allow re-opening by clicking/tapping the input again
        this.input.addEventListener('click', () => {
            if (activePinPad !== this) this._show();
        });
    }

    // ---------------------------------------------------------------- key handling

    _handleKey(key) {
        if (key === 'back') {
            this.input.value = this.input.value.slice(0, -1);
        } else if (key === 'clear') {
            this.input.value = '';
        } else if (this.input.value.length < 4) {
            this.input.value += key;
        }
        this._updateDots();

        // Auto-confirm when all 4 digits entered
        if (this.input.value.length === 4) {
            // Small delay so user sees all dots filled
            setTimeout(() => this._confirm(), 150);
        }
    }

    // ---------------------------------------------------------------- confirm / advance

    _confirm() {
        if (this.input.value.length !== 4) return;
        this._hide();

        // Auto-advance to the next PIN input in the same form if it's still empty
        const form = this.input.closest('form');
        if (form) {
            const pinInputs = Array.from(form.querySelectorAll('input[data-pin]'));
            const myIndex   = pinInputs.indexOf(this.input);
            const nextPin   = pinInputs[myIndex + 1];
            if (nextPin && !nextPin.value) {
                // Brief delay for UX
                setTimeout(() => nextPin.focus(), 100);
                return;
            }
            // Last PIN field — submit the form
            setTimeout(() => form.submit(), 150);
        }
    }

    // ---------------------------------------------------------------- show / hide

    _show() {
        if (activePinPad && activePinPad !== this) {
            activePinPad._hide();
        }
        activePinPad = this;
        this._updateDots();
        this.overlay.classList.add('active');
    }

    _hide() {
        this.overlay.classList.remove('active');
        if (activePinPad === this) activePinPad = null;
        // Return focus to body so scanner input isn't blocked
        document.activeElement && document.activeElement.blur();
    }

    // ---------------------------------------------------------------- dots display

    _updateDots() {
        const dots  = this.dotsEl.querySelectorAll('.dot');
        const count = this.input.value.length;
        dots.forEach((dot, i) => {
            dot.classList.toggle('filled', i < count);
        });
    }
}

// ---------------------------------------------------------------- physical keyboard

document.addEventListener('keydown', (e) => {
    if (!activePinPad) return;

    if (e.key >= '0' && e.key <= '9') {
        e.preventDefault();
        activePinPad._handleKey(e.key);
    } else if (e.key === 'Backspace') {
        e.preventDefault();
        activePinPad._handleKey('back');
    } else if (e.key === 'Delete') {
        e.preventDefault();
        activePinPad._handleKey('clear');
    } else if (e.key === 'Enter') {
        e.preventDefault();
        activePinPad._confirm();
    } else if (e.key === 'Escape') {
        e.preventDefault();
        activePinPad.input.value = '';
        activePinPad._updateDots();
        activePinPad._hide();
    }
});

// ---------------------------------------------------------------- auto-init

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[data-pin]').forEach(el => new PinPad(el));
});
