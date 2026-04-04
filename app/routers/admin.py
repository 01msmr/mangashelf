"""Admin endpoints: users, overdue, settings, rebuy."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Loan, Copy, Book, Transaction, RebuyItem, Setting
from ..dependencies import get_current_admin, get_current_user
from ..services.finance import LOAN_RATES, DEPOSIT

router = APIRouter(tags=['admin'])

_ADMIN_VERIFY_TTL = timedelta(minutes=10)


def _admin_session_key(user_id: int) -> str:
    return f'admin_ok_{user_id}'


def _is_admin_verified(request: Request, user_id: int) -> bool:
    until = request.session.get(_admin_session_key(user_id))
    return bool(until and until > datetime.now(timezone.utc).isoformat())


def _set_admin_verified(request: Request, user_id: int):
    request.session[_admin_session_key(user_id)] = (
        datetime.now(timezone.utc) + _ADMIN_VERIFY_TTL
    ).isoformat()


# ── Admin PIN gate ─────────────────────────────────────────────────────────────

class AdminVerifyRequest(BaseModel):
    pin: str


@router.get('/verified')
def admin_verified(request: Request, admin: User = Depends(get_current_admin)):
    """Check if admin section PIN has been recently verified."""
    if not _is_admin_verified(request, admin.id):
        raise HTTPException(403, 'Admin PIN verification required.')
    return {'ok': True}


@router.post('/verify')
def admin_verify(body: AdminVerifyRequest, request: Request,
                 admin: User = Depends(get_current_admin),
                 db: Session = Depends(get_db)):
    """Verify combined PIN (first 4 = user PIN, last 4 = admin PIN) to unlock admin section."""
    combined = body.pin.strip()
    if len(combined) != 8 or not combined.isdigit():
        raise HTTPException(401, 'Enter your 4-digit PIN followed by the 4-digit admin PIN.')
    user_pin  = combined[:4]
    admin_pin = combined[4:]
    stored_admin_pin = Setting.get(db, 'admin_pin', '0369')
    if not admin.check_pin(user_pin) or admin_pin != stored_admin_pin:
        raise HTTPException(401, 'Incorrect PIN combination.')
    _set_admin_verified(request, admin.id)
    return {'ok': True}


class SetAdminPinRequest(BaseModel):
    new_pin: str


@router.post('/set-admin-pin')
def set_admin_pin(body: SetAdminPinRequest, request: Request,
                  admin: User = Depends(get_current_admin),
                  db: Session = Depends(get_db)):
    """Change the shared admin PIN. Requires admin section to already be verified."""
    if not _is_admin_verified(request, admin.id):
        raise HTTPException(403, 'Admin PIN verification required.')
    pin = body.new_pin.strip()
    if len(pin) != 4 or not pin.isdigit():
        raise HTTPException(400, 'Admin PIN must be exactly 4 digits.')
    Setting.set(db, 'admin_pin', pin)
    db.commit()
    return {'ok': True, 'message': 'Admin PIN updated.'}



# ── User management ───────────────────────────────────────────────────────────

@router.get('/users')
def users(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    all_users = db.query(User).order_by(User.username).all()
    loan_counts = {u.id: db.query(Loan).filter_by(user_id=u.id).count() for u in all_users}
    now_iso = datetime.now(timezone.utc).isoformat()
    return [
        {
            'id':           u.id,
            'username':     u.username,
            'is_admin':     bool(u.is_admin),
            'active':       bool(u.active),
            'guthaben':     u.guthaben,
            'loan_count':   loan_counts[u.id],
            'created_at':   u.created_at,
        }
        for u in all_users
    ]


@router.post('/users/{user_id}/promote')
def user_promote(user_id: int, db: Session = Depends(get_db),
                 admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, 'User not found.')
    if user.id == admin.id:
        raise HTTPException(400, 'You cannot change your own admin status.')
    user.is_admin = 0 if user.is_admin else 1
    db.commit()
    action = 'promoted to admin' if user.is_admin else 'removed from admin'
    return {'ok': True, 'is_admin': bool(user.is_admin), 'message': f'"{user.username}" {action}.'}


@router.post('/users/{user_id}/deactivate')
def user_deactivate(user_id: int, db: Session = Depends(get_db),
                    admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, 'User not found.')
    if user.id == admin.id:
        raise HTTPException(400, 'You cannot deactivate yourself.')
    user.active = 0 if user.active else 1
    db.commit()
    state = 'unlocked' if user.active else 'locked'
    return {'ok': True, 'active': bool(user.active), 'message': f'"{user.username}" {state}.'}


@router.delete('/users/{user_id}')
def user_delete(user_id: int, db: Session = Depends(get_db),
                admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, 'User not found.')
    if user.id == admin.id:
        raise HTTPException(400, 'You cannot delete yourself.')
    open_loans = db.query(Loan).filter_by(user_id=user.id).count()
    if open_loans:
        raise HTTPException(400, f'Cannot delete "{user.username}" — they have {open_loans} open loan(s).')
    db.query(Transaction).filter_by(user_id=user.id).delete()
    db.delete(user)
    db.commit()
    return {'ok': True, 'message': f'"{user.username}" deleted.'}


class SetPinRequest(BaseModel):
    pin: str


@router.post('/users/{user_id}/set-pin')
def user_set_pin(user_id: int, body: SetPinRequest, db: Session = Depends(get_db),
                 _admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, 'User not found.')
    pin = body.pin.strip()
    if not pin.isdigit() or len(pin) != 4:
        raise HTTPException(400, 'PIN must be exactly 4 digits.')
    user.set_pin(pin)
    user.setup_required = 0
    db.commit()
    return {'ok': True, 'message': f'PIN updated for "{user.username}".'}


@router.post('/users/{user_id}/force-pin')
def user_force_pin(user_id: int, db: Session = Depends(get_db),
                   _admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, 'User not found.')
    user.setup_required = 1
    db.commit()
    return {'ok': True, 'message': f'"{user.username}" must set a new PIN on next login.'}


class AdjustRequest(BaseModel):
    amount: float
    reason: Optional[str] = None


@router.post('/users/{user_id}/adjust')
def user_adjust(user_id: int, body: AdjustRequest, db: Session = Depends(get_db),
                _admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, 'User not found.')

    amount = round(body.amount, 2)
    if amount == 0:
        raise HTTPException(400, 'Amount cannot be zero.')
    if amount < 0 and user.guthaben + amount < 0:
        raise HTTPException(400,
            f'Cannot debit {abs(amount):.2f} € — balance would go negative ({user.guthaben:.2f} €).')
    if amount > 0 and user.guthaben + amount > 100:
        raise HTTPException(400, 'Balance cannot exceed 100 €')

    reason = (body.reason or '').strip() or 'Admin adjustment'
    user.guthaben = round(user.guthaben + amount, 2)
    db.add(Transaction(
        user_id=user.id, amount=amount, type='manual',
        description=f'Admin: {reason}',
    ))
    db.commit()

    direction = 'credited' if amount > 0 else 'debited'
    return {
        'ok': True,
        'guthaben': user.guthaben,
        'message': f'"{user.username}": {abs(amount):.2f} € {direction}. New balance: {user.guthaben:.2f} €',
    }


# ── Purge empty books ─────────────────────────────────────────────────────────

@router.post('/purge-empty-books')
def purge_empty_books(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    """Delete all books where every copy is broken (or there are no copies)."""
    all_books = db.query(Book).all()
    removed = 0
    for book in all_books:
        if not any(c.status != 'broken' for c in book.copies):
            for copy in book.copies:
                db.delete(copy)
            db.delete(book)
            removed += 1
    db.commit()
    return {'ok': True, 'removed': removed, 'message': f'{removed} book(s) removed.'}


# ── Overdue ───────────────────────────────────────────────────────────────────

@router.get('/overdue')
def overdue(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    now_iso = datetime.now(timezone.utc).isoformat()
    now_dt  = datetime.now(timezone.utc)

    raw = (
        db.query(Loan)
        .join(Copy)
        .join(Book)
        .filter(Loan.due_date < now_iso)
        .order_by(Loan.due_date)
        .all()
    )

    result = []
    for loan in raw:
        try:
            due_dt = datetime.fromisoformat(loan.due_date.replace('Z', '+00:00'))
            days   = (now_dt - due_dt).days
        except Exception:
            days = 0
        result.append({
            'loan_id':    loan.id,
            'username':   loan.user.username,
            'user_active': bool(loan.user.active),
            'book_title': loan.copy.book.title if loan.copy and loan.copy.book else '',
            'book_isbn':  loan.copy.book.isbn  if loan.copy and loan.copy.book else '',
            'due_date':   loan.due_date,
            'days_overdue': days,
        })
    return result


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get('/settings')
def settings_get(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    return {
        'max_books_per_user': Setting.get_int(db, 'max_books_per_user', 3),
        'max_loan_days':      Setting.get_int(db, 'max_loan_days', 60),
        'default_loan_rate':  Setting.get(db, 'default_loan_rate', '0.50'),
        'new_book_days':      Setting.get_int(db, 'new_book_days', 14),
        'loan_rates':         LOAN_RATES,
    }


class SettingsRequest(BaseModel):
    max_books_per_user: int
    max_loan_days:      int
    default_loan_rate:  str
    new_book_days:      int


@router.post('/settings')
def settings_save(body: SettingsRequest, db: Session = Depends(get_db),
                  _admin: User = Depends(get_current_admin)):
    errors = []
    if not 1 <= body.max_books_per_user <= 20:
        errors.append('Max books must be between 1 and 20.')
    if not 7 <= body.max_loan_days <= 365:
        errors.append('Loan days must be between 7 and 365.')
    if body.default_loan_rate not in LOAN_RATES:
        errors.append('Invalid loan rate.')
    if not 0 <= body.new_book_days <= 90:
        errors.append('New book days must be between 0 and 90.')
    if errors:
        raise HTTPException(400, ' '.join(errors))

    Setting.set(db, 'max_books_per_user', body.max_books_per_user)
    Setting.set(db, 'max_loan_days',      body.max_loan_days)
    Setting.set(db, 'default_loan_rate',  body.default_loan_rate)
    Setting.set(db, 'new_book_days',      body.new_book_days)
    db.commit()
    return {'ok': True}


# ── Rebuy list ────────────────────────────────────────────────────────────────

@router.get('/rebuy')
def rebuy(db: Session = Depends(get_db), _admin: User = Depends(get_current_admin)):
    items = (
        db.query(RebuyItem)
        .filter_by(resolved=0)
        .order_by(RebuyItem.added_at.desc())
        .all()
    )
    return [
        {
            'id':          i.id,
            'book_title':  i.book.title  if i.book else '',
            'book_author': i.book.author if i.book else '',
            'book_isbn':   i.book.isbn   if i.book else '',
            'copy_num':    i.copy.copy_num if i.copy else None,
            'cover_path':  i.book.cover_path if i.book else None,
            'reason':      i.reason,
            'added_at':    i.added_at,
        }
        for i in items
    ]


@router.post('/rebuy/{item_id}/resolve')
def rebuy_resolve(item_id: int, db: Session = Depends(get_db),
                  _admin: User = Depends(get_current_admin)):
    item = db.get(RebuyItem, item_id)
    if not item:
        raise HTTPException(404, 'Item not found.')
    item.resolved = 1
    if item.copy:
        item.copy.status     = 'available'
        item.copy.broken_at  = None
        item.copy.broken_note = None
    db.commit()
    return {'ok': True, 'message': f'"{item.book.title}" marked as reacquired.'}


@router.delete('/rebuy/{item_id}')
def rebuy_dismiss(item_id: int, db: Session = Depends(get_db),
                  _admin: User = Depends(get_current_admin)):
    item = db.get(RebuyItem, item_id)
    if not item:
        raise HTTPException(404, 'Item not found.')
    db.delete(item)
    db.commit()
    return {'ok': True}
