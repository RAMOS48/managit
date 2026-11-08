"""Create (or reset) a user. The password is asked interactively and never
appears in the shell history.

Usage (from the backend folder, venv active):
    python create_user.py --username admin --role admin --full-name "IT Admin"
    python create_user.py --username amina --role employee --full-name "Amina B." --device-id 3
    python create_user.py --username amina --role employee --reset      # new password
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models.models import Device, User
from app.security.passwords import hash_password

MIN_LENGTH = 10


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", choices=["admin", "employee"], required=True)
    parser.add_argument("--full-name", default=None)
    parser.add_argument("--device-id", type=int, default=None)
    parser.add_argument("--reset", action="store_true", help="change the password of an existing user")
    args = parser.parse_args()

    username = args.username.strip()
    if not 2 <= len(username) <= 50:
        sys.exit("The username must be 2 to 50 characters.")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.scalars(select(User).where(User.username == username)).first()
        if existing and not args.reset:
            sys.exit(f"User '{username}' already exists. Use --reset to change the password.")
        if not existing and args.reset:
            sys.exit(f"User '{username}' does not exist.")
        if args.device_id is not None and db.get(Device, args.device_id) is None:
            sys.exit(f"Device {args.device_id} does not exist.")

        password = getpass.getpass(f"Password for {username} (min {MIN_LENGTH} characters): ")
        if len(password) < MIN_LENGTH:
            sys.exit(f"The password must have at least {MIN_LENGTH} characters.")
        if password != getpass.getpass("Repeat the password: "):
            sys.exit("The passwords do not match.")

        if existing:
            existing.password_hash = hash_password(password)
            print(f"Password updated for '{username}'.")
        else:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    role=args.role,
                    full_name=args.full_name,
                    linked_device_id=args.device_id,
                )
            )
            print(f"User '{username}' created with role '{args.role}'.")
        db.commit()


if __name__ == "__main__":
    main()
