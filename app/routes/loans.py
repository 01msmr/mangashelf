import io
import qrcode
from qrcode.image.pure import PyPNGImage
from datetime import datetime, timezone, timedelta
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, send_file)
from flask_login import login_required, current_user, login_user
from app import db
from app.models import Book, Copy, Loan, Setting, User
from app.services.finance import can_borrow, select_copy, charge_loan_fee, log_return
from app.services.network import get_lan_ip
from app.services.scan_tokens import make_token, consume_token

loans_bp = Blueprint('loans', __name__)

LOAN_RATES = ['0.50', '1.00', '1.50', '2.00']


def _phone_scan_url():
    """URL other devices on the LAN can use to reach the phone-scan page."""
    port = request.environ.get('SERVER_PORT', '5000')
    return f'https://{get_lan_ip()}:{port}/phone-scan'


# ── Main scan handler ─────────────────────────────────────────────────────────

@loans_bp.route('/scan/go')
@login_required
def scan_go():
    """GET endpoint for Shortcuts/widgets: /scan/go?isbn=XXX"""
    isbn = request.args.get('isbn', '').strip()
    return _process_scan(isbn)


@loans_bp.route('/mobile')
def mobile():
    """Entry point for users accessing MangaStore directly from their phone."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=url_for('loans.phone_scan')))
    return redirect(url_for('loans.phone_scan'))


@loans_bp.route('/phone-scan')
def phone_scan():
    """Phone camera scanner page. Auto-logs in via token if provided."""
    token = request.args.get('t')
    if token:
        user_id = consume_token(token)
        if user_id:
            user = db.session.get(User, user_id)
            if user:
                login_user(user)
        # Redirect to clean URL (strip token) so refreshes don't re-use it
        return redirect(url_for('loans.phone_scan'))

    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=url_for('loans.phone_scan')))

    return render_template('loans/phone_scan.html')


@loans_bp.route('/scan-qr.png')
@login_required
def scan_qr():
    """QR for the kiosk scan page — encodes the current user's token."""
    return _make_qr_response(_token_url(current_user.id))


@loans_bp.route('/user-qr/<int:user_id>.png')
@login_required
def user_qr(user_id):
    """Per-user QR for admin users page and account page."""
    return _make_qr_response(_token_url(user_id))


def _token_url(user_id):
    port  = request.environ.get('SERVER_PORT', '5000')
    token = make_token(user_id)
    return f'https://{get_lan_ip()}:{port}/phone-scan?t={token}'


def _make_qr_response(url):
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    # Inverted: white modules on dark background to match the dark UI
    img = qr.make_image(fill_color='#f0eef8', back_color='#1a1a2e')
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype='image/png', max_age=0)


@loans_bp.route('/scan', methods=['POST'])
@login_required
def scan_handler():
    isbn = request.form.get('isbn', '').strip()
    return _process_scan(isbn)


def _process_scan(isbn):
    if not isbn:
        return redirect(url_for('books.scan'))

    book = Book.query.filter_by(isbn=isbn).first()

    # Unknown ISBN
    if not book:
        if current_user.is_admin:
            return redirect(url_for('books.book_add', isbn=isbn))
        flash(f'ISBN {isbn} is not in the library.', 'warning')
        return redirect(url_for('books.scan'))

    # Does this user already have copies of this ISBN on loan?
    user_loans = (
        Loan.query
        .join(Copy)
        .filter(Copy.book_id == book.id, Loan.user_id == current_user.id)
        .all()
    )

    if user_loans:
        if len(user_loans) == 1:
            return redirect(url_for('loans.return_confirm', loan_id=user_loans[0].id))
        # Multiple copies of the same ISBN — need picker
        return redirect(url_for('loans.return_picker', isbn=isbn))

    # No active loan — go to take-out
    return redirect(url_for('loans.borrow', isbn=isbn))


# ── Take-out (borrow) ─────────────────────────────────────────────────────────

@loans_bp.route('/borrow/<isbn>', methods=['GET', 'POST'])
@login_required
def borrow(isbn):
    book = Book.query.filter_by(isbn=isbn).first_or_404()

    allowed, reason = can_borrow(current_user)
    copy, is_donor = select_copy(book, current_user)

    if not copy:
        flash('No copies of this book are currently available.', 'warning')
        return redirect(url_for('books.book_detail', isbn=isbn))

    if not allowed:
        if reason == 'balance_low':
            flash(
                f'Balance too low ({current_user.guthaben:.2f} \u20ac). '
                'You need more than 10.00 \u20ac to borrow.',
                'warning',
            )
        else:
            max_b = Setting.get_int('max_books_per_user', 3)
            flash(f'Loan limit reached (maximum {max_b} books at once).', 'warning')
        return redirect(url_for('books.book_detail', isbn=isbn))

    default_rate = Setting.get('default_loan_rate', '0.50')

    if request.method == 'POST':
        # Validate chosen rate
        chosen_rate_str = request.form.get('loan_rate', default_rate)
        if chosen_rate_str not in LOAN_RATES:
            chosen_rate_str = default_rate
        chosen_rate = float(chosen_rate_str)

        # Re-check atomically (another user may have taken the last copy)
        allowed2, _ = can_borrow(current_user)
        copy2, is_donor2 = select_copy(book, current_user)
        if not allowed2 or not copy2:
            flash('Could not complete — please scan again.', 'error')
            return redirect(url_for('books.scan'))

        fee      = charge_loan_fee(current_user, book, is_donor2, rate=chosen_rate)
        max_days = Setting.get_int('max_loan_days', 60)
        now      = datetime.now(timezone.utc)
        due      = now + timedelta(days=max_days)

        copy2.status = 'loaned'
        db.session.add(Loan(
            copy_id=copy2.id,
            user_id=current_user.id,
            taken_out_at=now.isoformat(),
            due_date=due.isoformat(),
            fee_charged=fee,
        ))
        db.session.commit()

        due_str = due.strftime('%d.%m.%Y')
        if is_donor2:
            flash(f'"{book.title}" taken out — free (your donated copy)! Due {due_str}.', 'success')
        else:
            flash(f'"{book.title}" taken out. {fee:.2f} \u20ac charged. Due {due_str}.', 'success')
        return redirect(url_for('books.scan'))

    # GET — show confirmation screen
    max_days = Setting.get_int('max_loan_days', 60)
    due_date = (datetime.now(timezone.utc) + timedelta(days=max_days)).strftime('%d.%m.%Y')

    return render_template('loans/takeout.html',
                           book=book,
                           copy=copy,
                           is_donor=is_donor,
                           loan_rates=LOAN_RATES,
                           default_rate=default_rate,
                           guthaben=current_user.guthaben,
                           due_date=due_date)


# ── Return (single copy) ──────────────────────────────────────────────────────

@loans_bp.route('/return/<int:loan_id>', methods=['GET', 'POST'])
@login_required
def return_confirm(loan_id):
    loan = db.session.get(Loan, loan_id)
    if not loan or loan.user_id != current_user.id:
        flash('Loan record not found.', 'error')
        return redirect(url_for('books.scan'))

    book = loan.copy.book

    if request.method == 'POST':
        log_return(current_user, book.title)
        loan.copy.status = 'available'
        db.session.delete(loan)
        db.session.commit()

        flash(f'"{book.title}" returned. Thank you!', 'success')
        return redirect(url_for('books.scan'))

    return render_template('loans/return.html', loan=loan, book=book)


# ── Return picker (multiple copies of same ISBN) ──────────────────────────────

@loans_bp.route('/return-pick/<isbn>')
@login_required
def return_picker(isbn):
    book = Book.query.filter_by(isbn=isbn).first_or_404()

    user_loans = (
        Loan.query
        .join(Copy)
        .filter(Copy.book_id == book.id, Loan.user_id == current_user.id)
        .order_by(Loan.taken_out_at)
        .all()
    )

    if not user_loans:
        return redirect(url_for('books.scan'))
    if len(user_loans) == 1:
        return redirect(url_for('loans.return_confirm', loan_id=user_loans[0].id))

    return render_template('loans/return_picker.html', book=book, loans=user_loans)
