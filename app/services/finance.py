"""
Financial logic: borrow eligibility, loan fee charging, return logging.
All DB writes go through the passed session — caller must commit.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.models import Transaction, Loan, Setting


def can_borrow(db: Session, user) -> tuple[bool, str | None]:
    if user.guthaben <= 10.00:
        return False, 'balance_low'
    max_books = Setting.get_int(db, 'max_books_per_user', 3)
    active = db.query(Loan).filter_by(user_id=user.id).count()
    if active >= max_books:
        return False, 'limit_reached'
    return True, None


def select_copy(book, user) -> tuple:
    available = [c for c in book.copies if c.status == 'available']
    if not available:
        return None, False
    for copy in available:
        if copy.donated_by == user.id:
            return copy, True
    return available[0], False


def charge_loan_fee(db: Session, user, book, is_donor: bool = False, rate: float = None) -> float:
    if is_donor:
        db.add(Transaction(
            user_id=user.id, amount=0.0, type='loan',
            description=f'Loan (donor copy — free): {book.title}',
        ))
        return 0.0

    fee = rate if rate is not None else book.loan_rate
    max_debit = round(user.guthaben - 0.01, 2)
    if fee > max_debit:
        fee = max_debit
    if fee <= 0:
        return 0.0

    user.guthaben = round(user.guthaben - fee, 2)
    db.add(Transaction(
        user_id=user.id, amount=-fee, type='loan',
        description=f'Loan: {book.title}',
    ))
    return fee


def log_return(db: Session, user, book_title: str):
    db.add(Transaction(
        user_id=user.id, amount=0.0, type='return',
        description=f'Returned: {book_title}',
    ))
