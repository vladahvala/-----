import getpass
import sqlite3
import sys

from app.auth_database import create_users_table, get_connection
from app.auth_server import RESERVED_NAMES, hash_password


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m app.create_user <username>")
        sys.exit(1)

    username = sys.argv[1]
    if username.lower() in RESERVED_NAMES:
        print("This username is reserved")
        sys.exit(1)

    password = getpass.getpass("Password (min 8 chars): ")
    if len(password) < 8:
        print("Password is too short")
        sys.exit(1)

    create_users_table()
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        connection.commit()
        print(f"User '{username}' created")
    except sqlite3.IntegrityError:
        print("User already exists")
        sys.exit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    main()