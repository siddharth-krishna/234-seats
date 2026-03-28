"""Authentication helpers: password hashing and session cookie signing."""

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

# Session cookies expire after 30 days
_SESSION_MAX_AGE = 60 * 60 * 24 * 30
_COOKIE_SALT = "session"


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches *hashed*."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_session_token(user_id: int) -> str:
    """Return a signed, time-stamped token encoding *user_id*.

    The token is safe to store in a browser cookie: it is URL-safe and
    signed with the application secret key, so it cannot be forged.
    """
    s = URLSafeTimedSerializer(settings.secret_key)
    return s.dumps(user_id, salt=_COOKIE_SALT)  # type: ignore[no-any-return]


def decode_session_token(token: str) -> int | None:
    """Decode a session token and return the user_id, or None if invalid/expired."""
    s = URLSafeTimedSerializer(settings.secret_key)
    try:
        user_id: int = s.loads(token, salt=_COOKIE_SALT, max_age=_SESSION_MAX_AGE)
        return user_id
    except (BadSignature, SignatureExpired):
        return None
