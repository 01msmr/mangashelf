/**
 * makePinField(container, label, count=4)
 * Renders a complete PIN entry (label, dots, numpad) inside container.
 * Returns { getValue, reset, showError, hideError }
 */
function makePinField(container, label, count) {
    count = count || 4;
    let pin = '';

    container.innerHTML = `
        <div class="pin-card-label">${label}</div>
        <div class="pf-error pin-error" style="display:none;margin-bottom:8px"></div>
        <div class="pinpad-dots pf-dots">
            ${Array.from({length: count}, () => '<div class="dot"></div>').join('')}
        </div>
        <div class="pinpad-grid">
            <button class="pinpad-key" data-k="1" type="button">1</button>
            <button class="pinpad-key" data-k="2" type="button">2</button>
            <button class="pinpad-key" data-k="3" type="button">3</button>
            <button class="pinpad-key" data-k="4" type="button">4</button>
            <button class="pinpad-key" data-k="5" type="button">5</button>
            <button class="pinpad-key" data-k="6" type="button">6</button>
            <button class="pinpad-key" data-k="7" type="button">7</button>
            <button class="pinpad-key" data-k="8" type="button">8</button>
            <button class="pinpad-key" data-k="9" type="button">9</button>
            <button class="pinpad-key" data-k="clear" type="button">C</button>
            <button class="pinpad-key" data-k="0" type="button">0</button>
            <button class="pinpad-key" data-k="back" type="button">⌫</button>
        </div>`;

    const dots = Array.from(container.querySelectorAll('.dot'));
    const errEl = container.querySelector('.pf-error');

    function update() {
        dots.forEach((d, i) => d.classList.toggle('filled', i < pin.length));
    }

    container.querySelectorAll('.pinpad-key').forEach(btn => {
        btn.addEventListener('pointerdown', e => {
            e.preventDefault();
            const k = btn.dataset.k;
            if (k === 'back')       pin = pin.slice(0, -1);
            else if (k === 'clear') pin = '';
            else if (pin.length < count) pin += k;
            update();
        });
    });

    return {
        getValue()       { return pin; },
        reset()          { pin = ''; update(); errEl.style.display = 'none'; },
        showError(msg)   { errEl.textContent = msg; errEl.style.display = 'block'; },
        hideError()      { errEl.style.display = 'none'; },
    };
}
