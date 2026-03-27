from functools import wraps
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, flash, g
from flask_login import login_required, current_user
from app import db
from app.models import User, Loan, Copy, Book, Transaction, RebuyItem, Setting

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

LOAN_RATES = ['0.50', '1.00', '1.50', '2.00']


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('books.scan'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.before_request
def require_admin():
    """Gate every admin route — also injects overdue count into g."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login', next=request.url))
    if not current_user.is_admin:
        flash('Admin access required.', 'error')
        return redirect(url_for('books.scan'))
    now_iso = datetime.now(timezone.utc).isoformat()
    g.overdue_count = Loan.query.filter(Loan.due_date < now_iso).count()


# ── User management ───────────────────────────────────────────────────────────

@admin_bp.route('/users')
def users():
    all_users = User.query.order_by(User.username).all()
    loan_counts = {
        u.id: Loan.query.filter_by(user_id=u.id).count()
        for u in all_users
    }
    return render_template('admin/users.html',
                           users=all_users,
                           loan_counts=loan_counts)


@admin_bp.route('/user/<int:user_id>/promote', methods=['POST'])
def user_promote(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))
    if user.id == current_user.id:
        flash('You cannot change your own admin status.', 'warning')
        return redirect(url_for('admin.users'))

    user.is_admin = 0 if user.is_admin else 1
    db.session.commit()
    action = 'promoted to admin' if user.is_admin else 'removed from admin'
    flash(f'"{user.username}" {action}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/user/<int:user_id>/adjust', methods=['POST'])
def user_adjust(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))

    try:
        amount = round(float(request.form.get('amount', '0')), 2)
    except ValueError:
        flash('Invalid amount.', 'error')
        return redirect(url_for('admin.users'))

    if amount == 0:
        flash('Amount cannot be zero.', 'warning')
        return redirect(url_for('admin.users'))

    if amount < 0 and user.guthaben + amount < 0:
        flash(
            f'Cannot debit {abs(amount):.2f} \u20ac — '
            f'balance would go negative ({user.guthaben:.2f} \u20ac).',
            'error',
        )
        return redirect(url_for('admin.users'))

    reason = request.form.get('reason', '').strip() or 'Admin adjustment'
    user.guthaben = round(user.guthaben + amount, 2)
    db.session.add(Transaction(
        user_id=user.id,
        amount=amount,
        type='manual',
        description=f'Admin: {reason}',
    ))
    db.session.commit()

    direction = 'credited' if amount > 0 else 'debited'
    flash(
        f'"{user.username}": {abs(amount):.2f} \u20ac {direction}. '
        f'New balance: {user.guthaben:.2f} \u20ac',
        'success',
    )
    return redirect(url_for('admin.users'))


# ── Overdue loans ─────────────────────────────────────────────────────────────

@admin_bp.route('/overdue')
def overdue():
    now_iso = datetime.now(timezone.utc).isoformat()
    now_dt  = datetime.now(timezone.utc)

    raw = (
        Loan.query
        .join(Copy)
        .join(Book)
        .filter(Loan.due_date < now_iso)
        .order_by(Loan.due_date)
        .all()
    )

    overdue_items = []
    for loan in raw:
        try:
            due_dt = datetime.fromisoformat(loan.due_date.replace('Z', '+00:00'))
            days   = (now_dt - due_dt).days
        except Exception:
            days = 0
        overdue_items.append({'loan': loan, 'days': days})

    return render_template('admin/overdue.html', overdue_items=overdue_items)


# ── Settings ──────────────────────────────────────────────────────────────────

@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        errors = []
        try:
            max_books = int(request.form.get('max_books_per_user', '3'))
            if not 1 <= max_books <= 20:
                errors.append('Max books must be between 1 and 20.')
        except ValueError:
            errors.append('Max books must be a whole number.')

        try:
            max_days = int(request.form.get('max_loan_days', '60'))
            if not 7 <= max_days <= 365:
                errors.append('Loan days must be between 7 and 365.')
        except ValueError:
            errors.append('Loan days must be a whole number.')

        rate = request.form.get('default_loan_rate', '0.50')
        if rate not in LOAN_RATES:
            errors.append('Invalid loan rate.')

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            Setting.set('max_books_per_user', max_books)
            Setting.set('max_loan_days',      max_days)
            Setting.set('default_loan_rate',  rate)
            db.session.commit()
            flash('Settings saved.', 'success')

        return redirect(url_for('admin.settings'))

    current = {
        'max_books_per_user': Setting.get_int('max_books_per_user', 3),
        'max_loan_days':      Setting.get_int('max_loan_days', 60),
        'default_loan_rate':  Setting.get('default_loan_rate', '0.50'),
    }
    return render_template('admin/settings.html',
                           current=current,
                           loan_rates=LOAN_RATES)


# ── Rebuy list ────────────────────────────────────────────────────────────────

@admin_bp.route('/rebuy')
def rebuy():
    items = (
        RebuyItem.query
        .filter_by(resolved=0)
        .order_by(RebuyItem.added_at.desc())
        .all()
    )
    return render_template('admin/rebuy.html', items=items)


@admin_bp.route('/rebuy/<int:item_id>/resolve', methods=['POST'])
def rebuy_resolve(item_id):
    item = db.session.get(RebuyItem, item_id)
    if not item:
        flash('Item not found.', 'error')
        return redirect(url_for('admin.rebuy'))
    item.resolved = 1
    db.session.commit()
    flash(f'"{item.book.title}" marked as reacquired.', 'success')
    return redirect(url_for('admin.rebuy'))
