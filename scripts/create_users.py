"""Create or reset a user account.

Usage:
    python scripts/create_users.py <username> <password> [--admin]
    python scripts/create_users.py alice s3cret
    python scripts/create_users.py admin s3cret --admin

If the username already exists the password (and admin flag) will be updated.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User
from app.services.auth import hash_password


def create_or_update_user(username: str, password: str, *, is_admin: bool) -> None:
    """Create a new user or update an existing one's password and admin flag."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username).first()
        if user is None:
            user = User(
                username=username,
                hashed_password=hash_password(password),
                is_admin=is_admin,
            )
            db.add(user)
            action = "Created"
        else:
            user.hashed_password = hash_password(password)
            user.is_admin = is_admin
            action = "Updated"
        db.commit()
        role = "admin" if is_admin else "user"
        print(f"{action} {role}: {username}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="Username")
    parser.add_argument("password", help="Plain-text password (will be hashed)")
    parser.add_argument("--admin", action="store_true", help="Grant admin privileges")
    args = parser.parse_args()
    create_or_update_user(args.username, args.password, is_admin=args.admin)
