from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Transaction

auth_bp = Blueprint('auth', __name__)


def _validate_pin(pin):
    """Returns an error string or None if the PIN is valid."""
    if not pin.isdigit():
        return 'PIN must contain only digits.'
    if len(pin) != 4:
        return 'PIN must be exactly 4 digits.'
    return None


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('books.scan'))

    if request.method == 'POST':
        username    = request.form.get('username', '').strip().lower()
        pin         = request.form.get('pin', '').strip()
        pin_confirm = request.form.get('pin_confirm', '').strip()

        error = None
        if not username:
            error = 'Username is required.'
        elif len(username) < 3:
            error = 'Username must be at least 3 characters.'
        elif not username.isalnum():
            error = 'Username may only contain letters and numbers.'
        elif User.query.filter_by(username=username).first():
            error = 'Username already taken.'
        else:
            pin_error = _validate_pin(pin)
            if pin_error:
                error = pin_error
            elif pin != pin_confirm:
                error = 'PINs do not match.'

        if error:
            flash(error, 'error')
            return render_template('auth/register.html', username=username)

        user = User(username=username)
        user.set_pin(pin)
        db.session.add(user)
        db.session.flush()

        db.session.add(Transaction(
            user_id=user.id,
            amount=10.00,
            type='entry_fee',
            description='Entry fee credited on account creation.',
        ))
        db.session.commit()

        login_user(user)
        flash('Account created! 10.00 Euro entry fee added to your account.', 'success')
        return redirect(url_for('books.scan'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('books.scan'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        pin      = request.form.get('pin', '').strip()

        user = User.query.filter_by(username=username, active=1).first()
        if not user or not user.check_pin(pin):
            error = 'Unknown username.' if not user else 'Wrong PIN.'
            return render_template('auth/login.html', username=username, login_error=error)

        login_user(user)

        if user.setup_required:
            return redirect(url_for('auth.setup_pin'))

        return redirect(request.args.get('next') or url_for('books.scan'))

    return render_template('auth/login.html')


@auth_bp.route('/api/users')
def user_suggestions():
    q = request.args.get('q', '').strip().lower()
    if len(q) < 1:
        return jsonify([])
    users = User.query.filter(
        User.username.like(f'{q}%'),
        User.active == 1
    ).order_by(User.username).limit(8).all()
    return jsonify([u.username for u in users])


@auth_bp.route('/setup-pin', methods=['GET', 'POST'])
@login_required
def setup_pin():
    if not current_user.setup_required:
        return redirect(url_for('books.scan'))

    if request.method == 'POST':
        pin         = request.form.get('pin', '').strip()
        pin_confirm = request.form.get('pin_confirm', '').strip()

        error = _validate_pin(pin)
        if error:
            flash(error, 'error')
        elif pin == '0000':
            flash('You must choose a different PIN (not 0000).', 'error')
        elif pin != pin_confirm:
            flash('PINs do not match.', 'error')
        else:
            current_user.set_pin(pin)
            current_user.setup_required = 0
            db.session.commit()
            flash('PIN updated. Welcome, admin!', 'success')
            return redirect(url_for('books.scan'))

    return render_template('auth/setup_pin.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
