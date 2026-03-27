"""Book CRUD and admin book management endpoints."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Book, Copy, Loan, User, RebuyItem
from ..dependencies import get_current_user, get_current_admin
from ..services.isbn_lookup import lookup_isbn
from ..services.cover_cache import get_cover_path

router = APIRouter(tags=['books'])


# ── Book list ─────────────────────────────────────────────────────────────────

@router.get('/books')
def book_list(q: str = '', db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    query = db.query(Book)
    if q:
        like = f'%{q}%'
        query = query.filter(or_(Book.title.ilike(like), Book.author.ilike(like)))
    books = query.order_by(Book.title).all()

    result = []
    for book in books:
        available  = len(book.available_copies)
        loaned_cps = book.loaned_copies
        latest_due = None
        borrowers  = []
        for copy in loaned_cps:
            loan = db.query(Loan).filter_by(copy_id=copy.id).first()
            if loan:
                if latest_due is None or loan.due_date > latest_due:
                    latest_due = loan.due_date
                if user.is_admin:
                    borrowers.append(loan.user.username)
        result.append({
            'id':         book.id,
            'isbn':       book.isbn,
            'title':      book.title,
            'author':     book.author,
            'cover_path': book.cover_path,
            'loan_rate':  book.loan_rate,
            'available':  available,
            'loaned':     len(loaned_cps),
            'latest_due': latest_due,
            'borrowers':  borrowers,
        })
    return result


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

    return {
        'id':             book.id,
        'isbn':           book.isbn,
        'title':          book.title,
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
    }


# ── Fetch ISBN metadata (admin) ───────────────────────────────────────────────

@router.get('/books/fetch-isbn')
def fetch_isbn(isbn: str = '', _admin: User = Depends(get_current_admin)):
    if not isbn:
        raise HTTPException(400, 'ISBN required')
    meta = lookup_isbn(isbn.strip())
    if not meta or not meta.get('title'):
        raise HTTPException(404, 'Not found in OpenLibrary or Google Books')
    return meta


# ── Add book (admin) ──────────────────────────────────────────────────────────

class AddBookRequest(BaseModel):
    isbn:      str
    title:     str
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

    if db.query(Book).filter_by(isbn=isbn_val).first():
        raise HTTPException(409, 'A book with this ISBN already exists.')

    cover_path = get_cover_path(isbn_val, body.cover_url) if body.cover_url else None

    book = Book(
        isbn=isbn_val,
        title=title,
        author=body.author or None,
        publisher=body.publisher or None,
        published=body.published or None,
        cover_path=cover_path,
        added_by=admin.id,
        loan_rate=body.loan_rate if body.loan_rate is not None else 0.50,
    )
    db.add(book)
    db.flush()

    copy = Copy(
        book_id=book.id,
        copy_num=1,
        donated_by=body.donor_id,
    )
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
        reason=note or 'Marked as broken/unusable',
    ))

    book       = copy.book
    book_isbn  = book.isbn
    book_title = book.title

    remaining = [c for c in book.copies if c.id != copy.id and c.status in ('available', 'loaned')]
    if not remaining:
        db.delete(book)
        db.commit()
        return {'ok': True, 'book_removed': True, 'message': f'Last copy — book "{book_title}" removed.'}

    db.commit()
    return {'ok': True, 'book_removed': False, 'isbn': book_isbn}
