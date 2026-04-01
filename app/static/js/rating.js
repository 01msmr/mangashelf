/**
 * Rating slider widget — 0 (skip / no rating) through 9.
 *
 * Usage:
 *   const slider = createRatingSlider(containerEl, initialValue);
 *   slider.getValue();   // current 0–9
 *   slider.setValue(5);  // set programmatically
 */
function createRatingSlider(container, initial) {
    let value = Math.max(0, Math.min(9, initial || 0));

    container.innerHTML = `
        <div class="rs-track" id="rs-track">
            <div class="rs-line"></div>
            <div class="rs-fill" id="rs-fill"></div>
            <div class="rs-puck" id="rs-puck"></div>
        </div>
        <div class="rs-nums" id="rs-nums">
            ${[0,1,2,3,4,5,6,7,8,9].map(i =>
                `<span class="rs-num" data-v="${i}">${i === 0 ? '·' : i}</span>`
            ).join('')}
        </div>`;

    const track = container.querySelector('#rs-track');
    const puck  = container.querySelector('#rs-puck');
    const fill  = container.querySelector('#rs-fill');
    const nums  = container.querySelectorAll('.rs-num');

    function pct(v) { return (v / 9) * 100; }

    function render(v) {
        puck.style.left = pct(v) + '%';
        puck.classList.toggle('rs-zero', v === 0);

        if (v > 0) {
            fill.style.left  = pct(1) + '%';
            fill.style.width = Math.max(0, pct(v) - pct(1)) + '%';
            fill.style.display = '';
        } else {
            fill.style.display = 'none';
        }

        nums.forEach(n => {
            const nv = +n.dataset.v;
            n.classList.toggle('rs-num-active', nv === v);
            n.classList.toggle('rs-num-zero',   nv === 0);
        });
    }

    function snapX(clientX) {
        const r = track.getBoundingClientRect();
        const ratio = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
        return Math.round(ratio * 9);
    }

    function set(v) { value = v; render(v); }

    /* ── tap on track ── */
    track.addEventListener('click', e => {
        if (e.target === puck) return;
        set(snapX(e.clientX));
    });

    /* ── tap on number labels ── */
    nums.forEach(n => n.addEventListener('click', () => set(+n.dataset.v)));

    /* ── drag puck (pointer events — works for touch + mouse) ── */
    let dragging = false;
    puck.addEventListener('pointerdown', e => {
        dragging = true;
        puck.setPointerCapture(e.pointerId);
        e.preventDefault();
    });
    puck.addEventListener('pointermove', e => {
        if (!dragging) return;
        set(snapX(e.clientX));
    });
    puck.addEventListener('pointerup',     () => { dragging = false; });
    puck.addEventListener('pointercancel', () => { dragging = false; });

    set(value);
    return {
        getValue: ()  => value,
        setValue: (v) => set(Math.max(0, Math.min(9, v))),
    };
}
