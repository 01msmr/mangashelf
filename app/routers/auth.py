"""Auth endpoints: login, logout, register, setup-pin, user suggestions."""
from __future__ import annotations
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Transaction
from ..dependencies import get_current_user

router = APIRouter(tags=['auth'])

# ── Login rate limiting ────────────────────────────────────────────────────────
# Per-username: lock for LOCKOUT_SECONDS after LOCKOUT_ATTEMPTS consecutive failures.
_login_attempts: dict[str, dict] = {}
LOCKOUT_ATTEMPTS = 4
LOCKOUT_SECONDS  = 120


def _validate_pin(pin: str) -> str | None:
    if not pin.isdigit():
        return 'PIN must contain only digits.'
    if len(pin) != 4:
        return 'PIN must be exactly 4 digits.'
    return None


# ── Login / logout ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    pin: str


@router.post('/auth/login')
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    now      = time.time()

    state = _login_attempts.get(username, {'count': 0, 'locked_until': 0.0})
    if state['locked_until'] > now:
        wait = int(state['locked_until'] - now) + 1
        return JSONResponse(
            status_code=429,
            content={'detail': f'Too many failed attempts. Try again in {wait}s.', 'wait_seconds': wait},
        )

    user = db.query(User).filter_by(username=username, active=1).first()
    if not user or not user.check_pin(body.pin.strip()):
        count = state['count'] + 1
        locked_until = (now + LOCKOUT_SECONDS) if count >= LOCKOUT_ATTEMPTS else 0.0
        _login_attempts[username] = {'count': count, 'locked_until': locked_until}
        if locked_until:
            return JSONResponse(
                status_code=429,
                content={'detail': f'Too many failed attempts. Try again in {LOCKOUT_SECONDS}s.', 'wait_seconds': LOCKOUT_SECONDS},
            )
        raise HTTPException(status_code=401, detail='Wrong PIN.' if user else 'Unknown username.')

    _login_attempts.pop(username, None)
    request.session['user_id'] = str(user.id)
    return {'ok': True, 'setup_required': bool(user.setup_required), 'is_admin': bool(user.is_admin)}


@router.post('/auth/logout')
def logout(request: Request):
    request.session.clear()
    return {'ok': True}


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    pin: str
    pin_confirm: str


@router.post('/auth/register')
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    pin      = body.pin.strip()

    if not username:
        raise HTTPException(400, 'Username is required.')
    if len(username) < 3:
        raise HTTPException(400, 'Username must be at least 3 characters.')
    if not username.isalnum():
        raise HTTPException(400, 'Username may only contain letters and numbers.')
    if db.query(User).filter_by(username=username).first():
        raise HTTPException(409, 'Username already taken.')

    err = _validate_pin(pin)
    if err:
        raise HTTPException(400, err)
    if pin != body.pin_confirm.strip():
        raise HTTPException(400, 'PINs do not match.')

    user = User(username=username)
    user.set_pin(pin)
    db.add(user)
    db.flush()

    db.add(Transaction(
        user_id=user.id,
        amount=10.00,
        type='entry_fee',
        description='Entry fee credited on account creation.',
    ))
    db.commit()

    request.session['user_id'] = str(user.id)
    return {'ok': True, 'message': 'Account created! 10.00 € entry fee added.'}


# ── Setup PIN (admin first-login) ─────────────────────────────────────────────

class SetupPinRequest(BaseModel):
    pin: str
    pin_confirm: str


@router.post('/auth/setup-pin')
def setup_pin(body: SetupPinRequest, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    if not user.setup_required:
        raise HTTPException(400, 'No PIN setup required.')

    pin = body.pin.strip()
    err = _validate_pin(pin)
    if err:
        raise HTTPException(400, err)
    if pin == '0000':
        raise HTTPException(400, 'You must choose a different PIN (not 0000).')
    if pin != body.pin_confirm.strip():
        raise HTTPException(400, 'PINs do not match.')

    user.set_pin(pin)
    user.setup_required = 0
    db.commit()
    return {'ok': True}


# ── Current user info ─────────────────────────────────────────────────────────

@router.get('/auth/me')
def me(user: User = Depends(get_current_user)):
    return {
        'id':             user.id,
        'username':       user.username,
        'is_admin':       bool(user.is_admin),
        'guthaben':       user.guthaben,
        'setup_required': bool(user.setup_required),
    }


# ── Username autocomplete / full list ────────────────────────────────────────

@router.get('/users')
def user_suggestions(q: str = '', db: Session = Depends(get_db)):
    """Return matching usernames. If q is empty, return all active users (for login screen)."""
    q = q.strip().lower()
    query = db.query(User).filter(User.active == 1)
    if q:
        query = query.filter(User.username.like(f'{q}%'))
    users = query.order_by(User.username).limit(50).all()
    return [u.username for u in users]
