"""Book CRUD and admin book management endpoints."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Book, BookRating, Copy, Loan, User, RebuyItem, Setting
from ..dependencies import get_current_user, get_current_admin
from ..services.isbn_lookup import lookup_isbn
from ..services.cover_cache import get_cover_path

router = APIRouter(tags=['books'])


# ── Book list ─────────────────────────────────────────────────────────────────

@router.get('/books')
def book_list(q: str = '', available: bool = False, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    from ..services.finance import can_borrow
    borrow_allowed, borrow_reason = can_borrow(db, user)
    max_days     = Setting.get_int(db, 'max_loan_days', 60)
    projected_due = (datetime.now(timezone.utc) + timedelta(days=max_days)).isoformat()

    query = db.query(Book)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Book.title.ilike(like), Book.author.ilike(like)))
    books = query.order_by(Book.title).all()
    if available:
        books = [b for b in books if b.available_copies]

    result = []
    for book in books:
        avail_count = len(book.available_copies)
        loaned_cps  = book.loaned_copies
        latest_due  = None
        borrowers   = []
        for copy in loaned_cps:
            loan = db.query(Loan).filter_by(copy_id=copy.id).first()
            if loan:
                if latest_due is None or loan.due_date > latest_due:
                    latest_due = loan.due_date
                if user.is_admin:
                    borrowers.append(loan.user.username)

        user_loan = (
            db.query(Loan)
            .join(Copy)
            .filter(Copy.book_id == book.id, Loan.user_id == user.id)
            .first()
        )

        avg, rating_count = db.query(func.avg(BookRating.rating), func.count(BookRating.rating)).filter(BookRating.book_id == book.id).one()
        result.append({
            'id':             book.id,
            'isbn':           book.isbn,
            'title':          book.title,
            'subtitle':       book.subtitle,
            'author':         book.author,
            'cover_path':     book.cover_path,
            'loan_rate':      book.loan_rate,
            'available':      avail_count,
            'total_copies':   len(book.active_copies),
            'loaned':         len(loaned_cps),
            'latest_due':     latest_due,
            'borrowers':      borrowers,
            'avg_rating':     round(avg, 1) if avg else None,
            'rating_count':   rating_count,
            'user_loan_id':   user_loan.id if user_loan else None,
            'user_loan_due':  user_loan.due_date if user_loan and user_loan.due_date else None,
            'projected_due':  user_loan.due_date if user_loan else projected_due,
            'borrow_allowed': borrow_allowed,
            'borrow_reason':  borrow_reason,
            'added_at':       book.added_at,
        })
    new_book_days = Setting.get_int(db, 'new_book_days', 14)
    return {'items': result, 'new_book_days': new_book_days}


# ── Fetch ISBN metadata (admin) ───────────────────────────────────────────────

@router.get('/books/fetch-isbn')
def fetch_isbn(isbn: str = '', _admin: User = Depends(get_current_admin)):
    if not isbn:
        raise HTTPException(400, 'ISBN required')
    meta = lookup_isbn(isbn.strip())
    if not meta or not meta.get('title'):
        raise HTTPException(404, 'Not found in OpenLibrary or Google Books')
    return meta


# ── Book detail ───────────────────────────────────────────────────────────────

@router.get('/books/{isbn}')
def book_detail(isbn: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    book = db.query(Book).filter_by(isbn=isbn).first()
    if not book:
        raise HTTPException(404, 'Book not found')

    loans_info = []
    for copy in book.copies:
        if copy.status == 'loaned':
            loan = db.query(Loan).filter_by(copy_id=copy.id).first()
            if loan:
                info = {'copy_id': copy.id, 'copy_num': copy.copy_num, 'due_date': loan.due_date}
                if user.is_admin:
                    info['borrower'] = loan.user.username
                loans_info.append(info)

    user_loan = (
        db.query(Loan)
        .join(Copy)
        .filter(Copy.book_id == book.id, Loan.user_id == user.id)
        .first()
    )

    from ..services.finance import can_borrow
    allowed, reason = can_borrow(db, user)

    avg = db.query(func.avg(BookRating.rating)).filter(BookRating.book_id == book.id).scalar()
    ur  = db.query(BookRating).filter_by(book_id=book.id, user_id=user.id).first()

    return {
        'id':             book.id,
        'isbn':           book.isbn,
        'title':          book.title,
        'subtitle':       book.subtitle,
        'author':         book.author,
        'publisher':      book.publisher,
        'published':      book.published,
        'cover_path':     book.cover_path,
        'loan_rate':      book.loan_rate,
        'available':      len(book.available_copies),
        'loaned':         len(book.loaned_copies),
        'copies':         [{'id': c.id, 'copy_num': c.copy_num, 'status': c.status} for c in book.copies],
        'loans_info':     loans_info,
        'user_loan_id':   user_loan.id if user_loan else None,
        'borrow_allowed': allowed,
        'borrow_reason':  reason,
        'avg_rating':     round(avg, 1) if avg else None,
        'user_rating':    ur.rating if ur else None,
    }


# ── Add book (admin) ──────────────────────────────────────────────────────────

class AddBookRequest(BaseModel):
    isbn:      str
    title:     str
    subtitle:  Optional[str] = None
    author:    Optional[str] = None
    publisher: Optional[str] = None
    published: Optional[str] = None
    cover_url: Optional[str] = None
    donor_id:  Optional[int] = None
    loan_rate: Optional[float] = None


@router.post('/books')
def book_add(body: AddBookRequest, db: Session = Depends(get_db),
             admin: User = Depends(get_current_admin)):
    isbn_val = body.isbn.strip()
    title    = body.title.strip()

    if not isbn_val or not title:
        raise HTTPException(400, 'ISBN and title are required.')

    existing = db.query(Book).filter_by(isbn=isbn_val).first()
    if existing:
        next_num = max((c.copy_num for c in existing.copies), default=0) + 1
        copy = Copy(book_id=existing.id, copy_num=next_num, donated_by=body.donor_id)
        db.add(copy)
        db.commit()
        return {'ok': True, 'isbn': isbn_val, 'title': existing.title}

    cover_path = get_cover_path(isbn_val, body.cover_url) if body.cover_url else None

    book = Book(
        isbn=isbn_val,
        title=title,
        subtitle=body.subtitle or None,
        author=body.author or None,
        publisher=body.publisher or None,
        published=body.published or None,
        cover_path=cover_path,
        added_by=admin.id,
        loan_rate=body.loan_rate if body.loan_rate is not None else 0.50,
    )
    db.add(book)
    db.flush()

    copy = Copy(book_id=book.id, copy_num=1, donated_by=body.donor_id)
    db.add(copy)
    db.commit()

    return {'ok': True, 'isbn': isbn_val, 'title': title}


# ── Mark copy as broken (admin) ───────────────────────────────────────────────

class BrokenRequest(BaseModel):
    broken_note: Optional[str] = None


@router.post('/copies/{copy_id}/broken')
def copy_mark_broken(copy_id: int, body: BrokenRequest, db: Session = Depends(get_db),
                     _admin: User = Depends(get_current_admin)):
    copy = db.get(Copy, copy_id)
    if not copy:
        raise HTTPException(404, 'Copy not found')

    note = (body.broken_note or '').strip() or None
    copy.status      = 'broken'
    copy.broken_at   = datetime.now(timezone.utc).isoformat()
    copy.broken_note = note

    db.add(RebuyItem(
        book_id=copy.book_id,
        copy_id=copy.id,
        reason=note or None,
    ))
    db.commit()
    return {'ok': True, 'book_removed': False, 'isbn': copy.book.isbn}


# ── Rate book ─────────────────────────────────────────────────────────────────

class RateRequest(BaseModel):
    rating: int   # 0 = clear existing, 1–9 = set / overwrite


@router.post('/books/{isbn}/rate')
def book_rate(isbn: str, body: RateRequest, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    if body.rating < 0 or body.rating > 9:
        raise HTTPException(400, 'Rating must be 0–9')
    book = db.query(Book).filter_by(isbn=isbn).first()
    if not book:
        raise HTTPException(404, 'Book not found')

    existing = db.query(BookRating).filter_by(book_id=book.id, user_id=user.id).first()

    if body.rating == 0:
        if existing:
            db.delete(existing)
            db.commit()
        return {'ok': True, 'rating': 0}

    if existing:
        existing.rating   = body.rating
        existing.rated_at = datetime.now(timezone.utc).isoformat()
    else:
        db.add(BookRating(book_id=book.id, user_id=user.id, rating=body.rating))
    db.commit()
    return {'ok': True, 'rating': body.rating}
