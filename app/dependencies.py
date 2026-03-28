"""FastAPI dependencies for authentication and authorisation."""

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.auth import decode_session_token

COOKIE_NAME = "session"


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> User | None:
    """Return the logged-in User, or None if the request is unauthenticated.

    Reads the signed session cookie, verifies it, and loads the user from
    the database. Returns None (rather than raising) so that pages can
    show different content to anonymous vs. logged-in visitors.
    """
    if session is None:
        return None
    user_id = decode_session_token(session)
    if user_id is None:
        return None
    return db.get(User, user_id)


def require_login(current_user: User | None = Depends(get_current_user)) -> User:
    """Dependency that requires an authenticated user.

    Raises 401 if the request is unauthenticated. Use this on routes that
    must be accessed by any logged-in user.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return current_user


def require_admin(current_user: User = Depends(require_login)) -> User:
    """Dependency that requires an admin user.

    Raises 403 if the logged-in user is not an admin.
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
