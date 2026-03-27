"""Account endpoints: PIN gate, top-up, change PIN, language."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Loan, Copy, Transaction, User
from ..dependencies import get_current_user

router = APIRouter(tags=['account'])

_TOPUP_MAX  = 50.00
_VERIFY_TTL = timedelta(minutes=5)
_SUPPORTED_LANGS = ['en', 'de', 'schwaebisch']


def _session_key(user_id: int) -> str:
    return f'acct_ok_{user_id}'


def _is_verified(request: Request, user_id: int) -> bool:
    until = request.session.get(_session_key(user_id))
    return bool(until and until > datetime.now(timezone.utc).isoformat())


def _set_verified(request: Request, user_id: int):
    key = _session_key(user_id)
    request.session[key] = (datetime.now(timezone.utc) + _VERIFY_TTL).isoformat()


# ── PIN gate ──────────────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    pin: str


@router.post('/account/verify')
def verify_pin(body: VerifyRequest, request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if not user.check_pin(body.pin.strip()):
        raise HTTPException(401, 'Incorrect PIN.')
    _set_verified(request, user.id)
    return {'ok': True}


# ── Account info ──────────────────────────────────────────────────────────────

@router.get('/account')
def account_info(request: Request, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    if not _is_verified(request, user.id):
        raise HTTPException(403, 'PIN verification required')

    now_iso = datetime.now(timezone.utc).isoformat()

    active_loans = (
        db.query(Loan)
        .join(Copy)
        .filter(Loan.user_id == user.id)
        .order_by(Loan.due_date)
        .all()
    )

    recent_txns = (
        db.query(Transaction)
        .filter_by(user_id=user.id)
        .order_by(Transaction.id.desc())
        .limit(20)
        .all()
    )

    if user.guthaben > 10.00:
        balance_status = 'ok'
    elif user.guthaben > 0:
        balance_status = 'warn'
    else:
        balance_status = 'danger'

    return {
        'username':      user.username,
        'guthaben':      user.guthaben,
        'balance_status': balance_status,
        'now_iso':       now_iso,
        'active_loans':  [
            {
                'id':          l.id,
                'book_title':  l.copy.book.title if l.copy and l.copy.book else '',
                'book_isbn':   l.copy.book.isbn  if l.copy and l.copy.book else '',
                'due_date':    l.due_date,
                'overdue':     l.due_date < now_iso,
            }
            for l in active_loans
        ],
        'recent_txns': [
            {
                'id':          t.id,
                'amount':      t.amount,
                'type':        t.type,
                'description': t.description,
                'created_at':  t.created_at,
            }
            for t in recent_txns
        ],
        'lang': request.session.get('lang', 'en'),
    }


# ── Top-up ────────────────────────────────────────────────────────────────────

class TopupRequest(BaseModel):
    amount: float


@router.post('/account/topup')
def topup(body: TopupRequest, request: Request, db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    if not _is_verified(request, user.id):
        raise HTTPException(403, 'PIN verification required')

    amount = round(body.amount, 2)
    if amount <= 0:
        raise HTTPException(400, 'Amount must be greater than zero.')
    if amount > _TOPUP_MAX:
        raise HTTPException(400, f'Maximum top-up per transaction is {_TOPUP_MAX:.2f} €.')

    user.guthaben = round(user.guthaben + amount, 2)
    db.add(Transaction(
        user_id=user.id,
        amount=amount,
        type='topup',
        description=f'Self top-up: {amount:.2f} €',
    ))
    db.commit()

    return {'ok': True, 'guthaben': user.guthaben,
            'message': f'{amount:.2f} € added. New balance: {user.guthaben:.2f} €'}


# ── Change PIN ────────────────────────────────────────────────────────────────

class ChangePinRequest(BaseModel):
    current_pin: str
    pin:         str
    pin_confirm: str


@router.post('/account/change-pin')
def change_pin(body: ChangePinRequest, request: Request, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if not _is_verified(request, user.id):
        raise HTTPException(403, 'PIN verification required')

    if not user.check_pin(body.current_pin.strip()):
        raise HTTPException(400, 'Current PIN is incorrect.')

    new_pin = body.pin.strip()
    if not new_pin.isdigit() or len(new_pin) != 4:
        raise HTTPException(400, 'New PIN must be exactly 4 digits.')
    if new_pin == body.current_pin.strip():
        raise HTTPException(400, 'New PIN must be different from your current PIN.')
    if new_pin != body.pin_confirm.strip():
        raise HTTPException(400, 'PINs do not match.')

    user.set_pin(new_pin)
    db.commit()
    _set_verified(request, user.id)
    return {'ok': True}


# ── Language preference ───────────────────────────────────────────────────────

@router.post('/account/language/{lang}')
def set_language(lang: str, request: Request,
                 _user: User = Depends(get_current_user)):
    if lang in _SUPPORTED_LANGS:
        request.session['lang'] = lang
    return {'ok': True, 'lang': request.session.get('lang', 'en')}
