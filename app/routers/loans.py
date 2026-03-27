"""Loan endpoints: scan, borrow, return, QR images, phone-scan."""
from __future__ import annotations
import io
from datetime import datetime, timezone, timedelta
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Book, Copy, Loan, Setting, User
from ..dependencies import get_current_user
from ..services.finance import can_borrow, select_copy, charge_loan_fee, log_return
from ..services.network import get_lan_ip
from ..services.scan_tokens import make_token, consume_token

router       = APIRouter(tags=['loans'])
media_router = APIRouter(tags=['media'])

LOAN_RATES = ['0.50', '1.00', '1.50', '2.00']


def _token_url(user_id: int, port: int = 5001) -> str:
    token = make_token(user_id)
    return f'https://{get_lan_ip()}:{port}/phone-scan?t={token}'


def _make_qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='#f0eef8', back_color='#1a1a2e')
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


# ── Scan handler ──────────────────────────────────────────────────────────────

@router.get('/scan')
def scan_go(isbn: str = '', db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    """Determine what to do with an ISBN: borrow, return, or add."""
    isbn = isbn.strip()
    if not isbn:
        raise HTTPException(400, 'ISBN required')

    book = db.query(Book).filter_by(isbn=isbn).first()
    if not book:
        if user.is_admin:
            return {'action': 'add', 'isbn': isbn}
        raise HTTPException(404, f'ISBN {isbn} is not in the library.')

    user_loans = (
        db.query(Loan)
        .join(Copy)
        .filter(Copy.book_id == book.id, Loan.user_id == user.id)
        .all()
    )

    if user_loans:
        if len(user_loans) == 1:
            return {'action': 'return', 'loan_id': user_loans[0].id, 'isbn': isbn}
        return {'action': 'return_pick', 'isbn': isbn}

    return {'action': 'borrow', 'isbn': isbn}


# ── Borrow ────────────────────────────────────────────────────────────────────

@router.get('/borrow/{isbn}')
def borrow_info(isbn: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    book = db.query(Book).filter_by(isbn=isbn).first()
    if not book:
        raise HTTPException(404, 'Book not found')

    allowed, reason = can_borrow(db, user)
    copy, is_donor  = select_copy(book, user)

    if not copy:
        raise HTTPException(409, 'No copies currently available.')

    if not allowed:
        if reason == 'balance_low':
            raise HTTPException(402, f'Balance too low ({user.guthaben:.2f} €). Need more than 10.00 €.')
        max_b = Setting.get_int(db, 'max_books_per_user', 3)
        raise HTTPException(409, f'Loan limit reached (maximum {max_b} books).')

    max_days = Setting.get_int(db, 'max_loan_days', 60)
    due_date = (datetime.now(timezone.utc) + timedelta(days=max_days)).strftime('%d.%m.%Y')
    default_rate = Setting.get(db, 'default_loan_rate', '0.50')

    return {
        'book':         {'isbn': book.isbn, 'title': book.title, 'author': book.author,
                         'cover_path': book.cover_path},
        'copy_num':     copy.copy_num,
        'is_donor':     is_donor,
        'guthaben':     user.guthaben,
        'loan_rates':   LOAN_RATES,
        'default_rate': default_rate,
        'due_date':     due_date,
    }


class BorrowRequest(BaseModel):
    loan_rate: Optional[str] = None


@router.post('/borrow/{isbn}')
def borrow_confirm(isbn: str, body: BorrowRequest, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    book = db.query(Book).filter_by(isbn=isbn).first()
    if not book:
        raise HTTPException(404, 'Book not found')

    default_rate = Setting.get(db, 'default_loan_rate', '0.50')
    chosen_rate_str = body.loan_rate if body.loan_rate in LOAN_RATES else default_rate
    chosen_rate = float(chosen_rate_str)

    allowed, _ = can_borrow(db, user)
    copy, is_donor = select_copy(book, user)
    if not allowed or not copy:
        raise HTTPException(409, 'Could not complete — please scan again.')

    fee      = charge_loan_fee(db, user, book, is_donor, rate=chosen_rate)
    max_days = Setting.get_int(db, 'max_loan_days', 60)
    now      = datetime.now(timezone.utc)
    due      = now + timedelta(days=max_days)

    copy.status = 'loaned'
    db.add(Loan(
        copy_id=copy.id,
        user_id=user.id,
        taken_out_at=now.isoformat(),
        due_date=due.isoformat(),
        fee_charged=fee,
    ))
    db.commit()

    due_str = due.strftime('%d.%m.%Y')
    if is_donor:
        msg = f'"{book.title}" taken out — free (your donated copy)! Due {due_str}.'
    else:
        msg = f'"{book.title}" taken out. {fee:.2f} € charged. Due {due_str}.'

    return {'ok': True, 'message': msg, 'fee': fee, 'due_date': due_str}


# ── Return ────────────────────────────────────────────────────────────────────

@router.get('/return/{loan_id}')
def return_info(loan_id: int, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    loan = db.get(Loan, loan_id)
    if not loan or loan.user_id != user.id:
        raise HTTPException(404, 'Loan not found.')
    book = loan.copy.book
    return {
        'loan_id':  loan.id,
        'book':     {'isbn': book.isbn, 'title': book.title, 'author': book.author,
                     'cover_path': book.cover_path},
        'due_date': loan.due_date,
    }


@router.post('/return/{loan_id}')
def return_confirm(loan_id: int, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    loan = db.get(Loan, loan_id)
    if not loan or loan.user_id != user.id:
        raise HTTPException(404, 'Loan not found.')
    book = loan.copy.book

    log_return(db, user, book.title)
    loan.copy.status = 'available'
    db.delete(loan)
    db.commit()

    return {'ok': True, 'message': f'"{book.title}" returned. Thank you!'}


@router.get('/return-pick/{isbn}')
def return_picker(isbn: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    book = db.query(Book).filter_by(isbn=isbn).first()
    if not book:
        raise HTTPException(404, 'Book not found')

    user_loans = (
        db.query(Loan)
        .join(Copy)
        .filter(Copy.book_id == book.id, Loan.user_id == user.id)
        .order_by(Loan.taken_out_at)
        .all()
    )
    return {
        'book':  {'isbn': book.isbn, 'title': book.title},
        'loans': [{'id': l.id, 'copy_num': l.copy.copy_num, 'due_date': l.due_date}
                  for l in user_loans],
    }


# ── Phone-scan token auth ─────────────────────────────────────────────────────

@router.get('/mobile')
def mobile(request: Request):
    return RedirectResponse('/phone-scan')


@router.get('/phone-scan-token')
def phone_scan_token(t: str = '', request: Request = None,
                     db: Session = Depends(get_db)):
    """Consume a QR token and log the user in."""
    user_id = consume_token(t) if t else None
    if not user_id:
        raise HTTPException(401, 'Invalid or expired token')
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(401, 'User not found')
    request.session['user_id'] = str(user.id)
    return {'ok': True}


# ── QR images ─────────────────────────────────────────────────────────────────

@media_router.get('/scan-qr.png')
def scan_qr(request: Request, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    png = _make_qr_png(_token_url(user.id))
    return Response(content=png, media_type='image/png',
                    headers={'Cache-Control': 'no-store'})


@media_router.get('/user-qr/{user_id}.png')
def user_qr(user_id: int, request: Request, db: Session = Depends(get_db),
            _user: User = Depends(get_current_user)):
    png = _make_qr_png(_token_url(user_id))
    return Response(content=png, media_type='image/png',
                    headers={'Cache-Control': 'no-store'})
