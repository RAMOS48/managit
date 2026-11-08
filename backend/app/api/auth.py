import time

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.security.auth import (
    COOKIE_NAME,
    SESSION_HOURS,
    create_session,
    delete_session,
    get_current_user,
)
from app.security.passwords import DUMMY_HASH, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_FAILURES = 5
LOCK_SECONDS = 300
_failures: dict[str, list[float]] = {}   # "ip|username" -> times of failed logins


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


def _key(request: Request, username: str) -> str:
    ip = request.client.host if request.client else "?"
    return f"{ip}|{username.lower()}"


def _recent_failures(key: str) -> list[float]:
    cutoff = time.time() - LOCK_SECONDS
    times = [t for t in _failures.get(key, []) if t > cutoff]
    if times:
        _failures[key] = times
    else:
        _failures.pop(key, None)
    return times


def _user_info(user: User) -> dict:
    return {"username": user.username, "full_name": user.full_name, "role": user.role}


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if len(_failures) > 1000:
        _failures.clear()  # keeps memory bounded if someone floods random usernames

    key = _key(request, payload.username)
    if len(_recent_failures(key)) >= MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")

    user = db.scalars(select(User).where(User.username == payload.username)).first()
    # Always run a hash check so a wrong username and a wrong password take the same time
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        _failures.setdefault(key, []).append(time.time())
        raise HTTPException(status_code=401, detail="Invalid username or password")

    _failures.pop(key, None)
    token = create_session(db, user)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,    # JavaScript cannot read it
        samesite="lax",   # not sent on cross-site POST requests
        path="/",
        # secure=True needs HTTPS, which this lab does not have (see known limitations)
    )
    return _user_info(user)


@router.post("/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if session_token:
        delete_session(db, session_token)
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_info(user)
