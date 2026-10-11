"""Create or update the first production admin without storing a password in source."""

import argparse
import getpass

from app.core.db import SessionLocal, init_db
from app.core.security import hash_password
from app.models.entities import User


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a TECH TOYS admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Shop Admin")
    args = parser.parse_args()
    password = getpass.getpass("Admin password: ")
    if len(password) < 12:
        raise SystemExit("Use a password with at least 12 characters.")
    init_db()
    db = SessionLocal()
    try:
        email = args.email.strip().lower()
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(name=args.name.strip(), email=email, password_hash=hash_password(password), role="admin", is_active=True)
            db.add(user)
        else:
            user.name = args.name.strip()
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
        db.commit()
        print("Production admin is ready:", email)
    finally:
        db.close()


if __name__ == "__main__":
    main()
