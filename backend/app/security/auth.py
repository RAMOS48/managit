import hashlib
import secrets
from datetime import timedelta

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, UserSession, utcnow

COOKIE_NAME = "managit_session"
SESSION_HOURS = 8


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    """Create a session and return the raw token. Only its hash is stored."""
    db.execute(delete(UserSession).where(UserSession.expires_at < utcnow()))
    token = secrets.token_urlsafe(32)
    db.add(
        UserSession(
            token_hash=_hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(hours=SESSION_HOURS),
        )
    )
    db.commit()
    return token


def delete_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == _hash_token(token)))
    db.commit()


def get_current_user(
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    row = db.scalars(
        select(UserSession).where(UserSession.token_hash == _hash_token(session_token))
    ).first()
    if row is None or row.expires_at < utcnow():
        if row is not None:
            db.delete(row)
            db.commit()
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user
