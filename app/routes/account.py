from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from app import db
from app.models import Loan, Copy, Transaction, Setting
from app.routes.auth import _validate_pin
from app.services.i18n import SUPPORTED_LANGS, DEFAULT_LANG

_TOPUP_MAX = 50.00   # single transaction cap

account_bp = Blueprint('account', __name__)

# How long the re-PIN verification stays valid in the session (shared kiosk)
_VERIFY_TTL = timedelta(minutes=5)


def _session_key():
    return f'acct_ok_{current_user.id}'


def _is_verified():
    until = session.get(_session_key())
    return bool(until and until > datetime.now(timezone.utc).isoformat())


def _set_verified():
    session[_session_key()] = (datetime.now(timezone.utc) + _VERIFY_TTL).isoformat()


# ── Account landing (re-PIN gate) ─────────────────────────────────────────────

@account_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account_page():
    if _is_verified():
        return _render_account()

    if request.method == 'POST':
        pin = request.form.get('pin', '').strip()
        if current_user.check_pin(pin):
            _set_verified()
            return redirect(url_for('account.account_page'))
        flash('Incorrect PIN.', 'error')

    return render_template('account/verify.html')


def _render_account():
    now_iso = datetime.now(timezone.utc).isoformat()

    active_loans = (
        Loan.query
        .join(Copy)
        .filter(Loan.user_id == current_user.id)
        .order_by(Loan.due_date)
        .all()
    )

    recent_txns = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.id.desc())
        .limit(20)
        .all()
    )

    if current_user.guthaben > 10.00:
        balance_status = 'ok'
    elif current_user.guthaben > 0:
        balance_status = 'warn'
    else:
        balance_status = 'danger'

    return render_template(
        'account/index.html',
        active_loans=active_loans,
        recent_txns=recent_txns,
        now_iso=now_iso,
        balance_status=balance_status,
    )


# ── Self-service top-up ───────────────────────────────────────────────────────

@account_bp.route('/account/topup', methods=['POST'])
@login_required
def topup():
    if not _is_verified():
        flash('Please verify your PIN first.', 'warning')
        return redirect(url_for('account.account_page'))

    try:
        amount = round(float(request.form.get('amount', '0')), 2)
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('account.account_page'))

    if amount <= 0:
        flash('Amount must be greater than zero.', 'error')
        return redirect(url_for('account.account_page'))

    if amount > _TOPUP_MAX:
        flash(f'Maximum top-up per transaction is {_TOPUP_MAX:.2f} \u20ac.', 'error')
        return redirect(url_for('account.account_page'))

    current_user.guthaben = round(current_user.guthaben + amount, 2)
    db.session.add(Transaction(
        user_id=current_user.id,
        amount=amount,
        type='topup',
        description=f'Self top-up: {amount:.2f} \u20ac',
    ))
    db.session.commit()

    flash(f'{amount:.2f} \u20ac added. New balance: {current_user.guthaben:.2f} \u20ac', 'success')
    return redirect(url_for('account.account_page'))


# ── Change PIN ────────────────────────────────────────────────────────────────

@account_bp.route('/account/change-pin', methods=['GET', 'POST'])
@login_required
def change_pin():
    # Require current account verification before allowing PIN change
    if not _is_verified():
        flash('Please verify your PIN first.', 'warning')
        return redirect(url_for('account.account_page'))

    if request.method == 'POST':
        current_pin = request.form.get('current_pin', '').strip()
        new_pin     = request.form.get('pin', '').strip()
        pin_confirm = request.form.get('pin_confirm', '').strip()

        error = None
        if not current_user.check_pin(current_pin):
            error = 'Current PIN is incorrect.'
        else:
            error = _validate_pin(new_pin)
            if not error and new_pin == current_pin:
                error = 'New PIN must be different from your current PIN.'
            elif not error and new_pin != pin_confirm:
                error = 'PINs do not match.'

        if error:
            flash(error, 'error')
            return render_template('account/change_pin.html')


# ── Language preference ───────────────────────────────────────────────────────

        current_user.set_pin(new_pin)
        db.session.commit()
        # Refresh session verification timestamp so they don't need to re-enter
        _set_verified()
        flash('PIN changed successfully.', 'success')
        return redirect(url_for('account.account_page'))

    return render_template('account/change_pin.html')


# ── Language preference ───────────────────────────────────────────────────────

@account_bp.route('/account/language/<lang>', methods=['POST'])
@login_required
def set_language(lang):
    if lang in SUPPORTED_LANGS:
        session['lang'] = lang
    return redirect(request.referrer or url_for('account.account_page'))
