/**
 * scanner.js — Barcode scanner input handler.
 *
 * The USB HID scanner acts as a keyboard: it types the ISBN digits
 * then sends Enter.  A hidden #scan-input in base.html captures this
 * stream on every page and routes it to the scan state machine.
 *
 * Special case: when the add-book form's #isbn-input is visible,
 * scanned barcodes fill that field instead and trigger the Fetch button.
 */

document.addEventListener('DOMContentLoaded', () => {
    const scanInput = document.getElementById('scan-input');
    if (!scanInput) return;

    // ── Refocus logic ──────────────────────────────────────────────────────

    function shouldRefocus() {
        if (activePinPad) return false;          // PIN pad has focus
        const el  = document.activeElement;
        const tag = el ? el.tagName.toLowerCase() : '';
        // Don't steal focus from real user inputs (text fields, selects, etc.)
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return false;
        return true;
    }

    function refocus() {
        if (shouldRefocus()) scanInput.focus();
    }

    // Refocus after any tap/click that doesn't land on an input
    document.addEventListener('pointerup', () => setTimeout(refocus, 60));
    // Initial focus
    setTimeout(refocus, 200);

    // ── Capture scanner stream ─────────────────────────────────────────────

    scanInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const isbn = scanInput.value.trim();
            scanInput.value = '';
            if (isbn.length >= 10) {
                handleScan(isbn);
            }
            e.preventDefault();
        }
    });
});

// ── Route the scanned ISBN ─────────────────────────────────────────────────

function handleScan(isbn) {
    // If the add-book form's ISBN field is in the DOM and visible,
    // fill it and trigger the Fetch button instead of the global scan.
    const isbnField = document.getElementById('isbn-input');
    if (isbnField && isbnField.offsetParent !== null) {
        isbnField.value = isbn;
        const fetchBtn = document.getElementById('fetch-btn');
        if (fetchBtn) setTimeout(() => fetchBtn.click(), 80);
        return;
    }

    // Submit the global hidden scan form → POST /scan
    const hiddenIsbn = document.getElementById('scan-isbn-hidden');
    const scanForm   = document.getElementById('scan-form');
    if (hiddenIsbn && scanForm) {
        hiddenIsbn.value = isbn;
        scanForm.submit();
    }
}
