import os
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape

import bcrypt
import jwt
from fastapi import FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth_database import create_users_table, get_connection
from app.auth_models import UserLogin, UserRegister

SECRET_KEY = os.getenv("JWT_SECRET", "змініть-цей-секрет-на-довгий-випадковий-рядок")
ALGORITHM = "HS256"
TOKEN_HOURS = 8
COOKIE_NAME = "access_token"
RESERVED_NAMES = {"admin", "root"}

app = FastAPI(title="University Monitoring Auth Service")


@app.on_event("startup")
def startup():
    create_users_table()


def hash_password(password: str) -> str:
    # bcrypt приймає максимум 72 байти
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode()[:72], password_hash.encode())


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def authenticate(username: str, password: str):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    finally:
        connection.close()

    if row and check_password(password, row["password_hash"]):
        return row["username"]
    return None


def set_auth_cookie(response: Response, token: str):
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        max_age=TOKEN_HOURS * 3600,
    )


LOGIN_PAGE = """<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <title>Вхід</title>
  <style>
    body {{ font-family: sans-serif; background: #f2f4f7; display: flex;
           justify-content: center; align-items: center; height: 100vh; margin: 0; }}
    form {{ background: white; padding: 32px; border-radius: 8px; width: 300px;
            box-shadow: 0 2px 8px rgba(0,0,0,.15); }}
    h2 {{ margin-top: 0; }}
    input {{ width: 100%; padding: 8px; margin: 6px 0 14px; box-sizing: border-box; }}
    button {{ width: 100%; padding: 10px; background: #1f6feb; color: white;
              border: 0; border-radius: 4px; cursor: pointer; }}
    .error {{ color: #c62828; margin-bottom: 10px; }}
  </style>
</head>
<body>
  <form method="post" action="/auth/login-form">
    <h2>Моніторинг БД</h2>
    {error}
    <label>Логін</label>
    <input name="username" required autofocus>
    <label>Пароль</label>
    <input name="password" type="password" required>
    <button type="submit">Увійти</button>
  </form>
</body>
</html>"""


def render_login(error: str = "") -> str:
    block = f'<div class="error">{escape(error)}</div>' if error else ""
    return LOGIN_PAGE.format(error=block)


# ---------- JSON API ----------

@app.post("/register")
def register(user: UserRegister):
    if user.username.lower() in RESERVED_NAMES:
        raise HTTPException(status_code=403, detail="This username is reserved")

    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (user.username, hash_password(user.password)),
        )
        connection.commit()
        return {"message": "User registered successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Username already exists")
    finally:
        connection.close()


@app.post("/login")
def login(user: UserLogin, response: Response):
    username = authenticate(user.username, user.password)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token(username)
    set_auth_cookie(response, token)
    return {"message": "Login successful", "username": username, "access_token": token}


# ---------- Сторінка входу ----------

@app.get("/login-page", response_class=HTMLResponse)
def login_page():
    return render_login()


@app.post("/login-form")
def login_form(username: str = Form(...), password: str = Form(...)):
    name = authenticate(username, password)
    if name is None:
        return HTMLResponse(render_login("Невірний логін або пароль"), status_code=401)

    response = RedirectResponse("/", status_code=303)
    set_auth_cookie(response, create_token(name))
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/auth/login-page", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------- Перевірка для nginx ----------

@app.get("/verify")
def verify(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return Response(status_code=200, headers={"X-Auth-User": payload["sub"]})


@app.get("/health")
def health():
    return {"status": "ok"}