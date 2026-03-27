from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
import bcrypt

from .database import Base


class User(Base):
    __tablename__ = 'users'

    id             = Column(Integer, primary_key=True)
    username       = Column(Text, unique=True, nullable=False)
    pin_hash       = Column(Text, nullable=False)
    is_admin       = Column(Integer, default=0)
    setup_required = Column(Integer, default=0)
    guthaben       = Column(Float, default=10.00)
    active         = Column(Integer, default=1)
    created_at     = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())

    loans        = relationship('Loan', back_populates='user', foreign_keys='Loan.user_id')
    transactions = relationship('Transaction', back_populates='user')

    def set_pin(self, pin: str):
        self.pin_hash = bcrypt.hashpw(pin.encode(), bcrypt.gensalt()).decode()

    def check_pin(self, pin: str) -> bool:
        return bcrypt.checkpw(pin.encode(), self.pin_hash.encode())

    @property
    def can_borrow(self) -> bool:
        return self.guthaben > 10.00


class Book(Base):
    __tablename__ = 'books'

    id         = Column(Integer, primary_key=True)
    isbn       = Column(Text, unique=True, nullable=False)
    title      = Column(Text, nullable=False)
    author     = Column(Text)
    publisher  = Column(Text)
    published  = Column(Text)
    cover_path = Column(Text)
    loan_rate  = Column(Float, default=0.50)
    added_by   = Column(Integer, ForeignKey('users.id'))
    added_at   = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())

    copies = relationship('Copy', back_populates='book')
    adder  = relationship('User', foreign_keys=[added_by])

    @property
    def available_copies(self):
        return [c for c in self.copies if c.status == 'available']

    @property
    def loaned_copies(self):
        return [c for c in self.copies if c.status == 'loaned']

    @property
    def active_copies(self):
        return [c for c in self.copies if c.status in ('available', 'loaned')]


class Copy(Base):
    __tablename__ = 'copies'

    id          = Column(Integer, primary_key=True)
    book_id     = Column(Integer, ForeignKey('books.id'), nullable=False)
    copy_num    = Column(Integer, default=1)
    status      = Column(Text, default='available')  # available | loaned | broken
    donated_by  = Column(Integer, ForeignKey('users.id'), nullable=True)
    broken_at   = Column(Text)
    broken_note = Column(Text)

    book  = relationship('Book', back_populates='copies')
    donor = relationship('User', foreign_keys=[donated_by])
    loans = relationship('Loan', back_populates='copy')
    rebuy = relationship('RebuyItem', back_populates='copy')


class Loan(Base):
    __tablename__ = 'loans'

    id           = Column(Integer, primary_key=True)
    copy_id      = Column(Integer, ForeignKey('copies.id'), nullable=False)
    user_id      = Column(Integer, ForeignKey('users.id'), nullable=False)
    taken_out_at = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())
    due_date     = Column(Text, nullable=False)
    fee_charged  = Column(Float, default=0.0)
    overdue_fee  = Column(Float, default=0.0)

    copy = relationship('Copy', back_populates='loans')
    user = relationship('User', back_populates='loans', foreign_keys=[user_id])


class Transaction(Base):
    __tablename__ = 'transactions'

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount      = Column(Float, nullable=False)
    type        = Column(Text, nullable=False)
    description = Column(Text)
    created_at  = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())

    user = relationship('User', back_populates='transactions')


class RebuyItem(Base):
    __tablename__ = 'rebuy_list'

    id       = Column(Integer, primary_key=True)
    book_id  = Column(Integer, ForeignKey('books.id'), nullable=False)
    copy_id  = Column(Integer, ForeignKey('copies.id'), nullable=True)
    reason   = Column(Text)
    added_at = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())
    resolved = Column(Integer, default=0)

    book = relationship('Book', foreign_keys=[book_id])
    copy = relationship('Copy', back_populates='rebuy')


class Setting(Base):
    __tablename__ = 'settings'

    key   = Column(Text, primary_key=True)
    value = Column(Text, nullable=False)

    @classmethod
    def get(cls, db, key: str, default=None):
        row = db.get(cls, key)
        return row.value if row else default

    @classmethod
    def get_int(cls, db, key: str, default: int = 0) -> int:
        return int(cls.get(db, key, default))

    @classmethod
    def get_float(cls, db, key: str, default: float = 0.0) -> float:
        return float(cls.get(db, key, default))

    @classmethod
    def set(cls, db, key: str, value):
        row = db.get(cls, key)
        if row:
            row.value = str(value)
        else:
            db.add(cls(key=key, value=str(value)))
