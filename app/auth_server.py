import hashlib
import sqlite3

from fastapi import FastAPI, HTTPException
from app.auth_database import create_users_table, get_connection
from app.auth_models import UserRegister, UserLogin

app = FastAPI(title="University Monitoring Auth Service")


@app.on_event("startup")
def startup():
    create_users_table()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


@app.post("/register")
def register(user: UserRegister):
    connection = get_connection()

    try:
        password_hash = hash_password(user.password)

        connection.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (?, ?)
            """,
            (user.username, password_hash)
        )

        connection.commit()

        return {"message": "User registered successfully"}

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    finally:
        connection.close()


@app.post("/login")
def login(user: UserLogin):
    connection = get_connection()

    try:
        password_hash = hash_password(user.password)

        result = connection.execute(
            """
            SELECT id, username
            FROM users
            WHERE username = ? AND password_hash = ?
            """,
            (user.username, password_hash)
        ).fetchone()

        if result is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid username or password"
            )

        return {
            "message": "Login successful",
            "user_id": result["id"],
            "username": result["username"]
        }

    finally:
        connection.close()


@app.get("/health")
def health():
    return {"status": "ok"}