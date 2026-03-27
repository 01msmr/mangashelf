from __future__ import annotations
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get('user_id')
    if not user_id:
        raise HTTPException(status_code=401, detail='Not authenticated')
    user = db.get(User, int(user_id))
    if not user or not user.active:
        raise HTTPException(status_code=401, detail='Not authenticated')
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='Admin required')
    return user


def require_account_verified(request: Request, user: User = Depends(get_current_user)) -> User:
    """Secondary PIN gate for the account page (shared kiosk)."""
    key   = f'acct_ok_{user.id}'
    until = request.session.get(key)
    if not until or until <= datetime.now(timezone.utc).isoformat():
        raise HTTPException(status_code=403, detail='PIN verification required')
    return user
