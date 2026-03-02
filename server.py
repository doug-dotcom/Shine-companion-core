import os
import json
import time
import sqlite3
import jwt

from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from openai import OpenAI

APP_TITLE = "Shine Companion"

USERS_PATH = os.getenv("USERS_PATH", "users.json")
DB_PATH = os.getenv("MEMORY_DB_PATH", "memory.db")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-please")
JWT_ALG = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "24"))

SHINE_MODEL = os.getenv("SHINE_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

app = FastAPI(title=APP_TITLE)

bearer = HTTPBearer(auto_error=False)

client = OpenAI(api_key=OPENAI_API_KEY)

# -------------------------
# DATABASE INIT
# -------------------------

def db_init():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS user_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        key TEXT,
        value TEXT,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

db_init()

# -------------------------
# USERS
# -------------------------

_users_cache = {"time": 0, "data": {}}

def load_users():
    try:
        st = os.stat(USERS_PATH)
    except FileNotFoundError:
        return {}

    if st.st_mtime != _users_cache["time"]:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)

        cooked = {}
        for k, v in raw.items():
            cooked[str(k).strip().lower()] = str(v)

        _users_cache["time"] = st.st_mtime
        _users_cache["data"] = cooked

    return _users_cache["data"]


def verify_user(username, password):
    users = load_users()
    username = username.strip().lower()

    if username not in users:
        return False

    return users[username] == password


# -------------------------
# JWT
# -------------------------

def create_token(user_id):
    payload = {
        "id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_HOURS)
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")

    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload["id"]
    except:
        raise HTTPException(status_code=401, detail="Invalid token")


# -------------------------
# MEMORY
# -------------------------

def load_user_memory(user_id):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT key, value FROM user_memory WHERE user_id=? ORDER BY created DESC LIMIT 20",
        (user_id,)
    )

    rows = cursor.fetchall()
    conn.close()

    memory_text = "\n".join([f"{k}: {v}" for k, v in rows])

    return memory_text


def save_user_memory(user_id, key, value):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO user_memory (user_id, key, value) VALUES (?, ?, ?)",
        (user_id, key, value)
    )

    conn.commit()
    conn.close()


# -------------------------
# REQUEST MODEL
# -------------------------

class ChatRequest(BaseModel):
    message: str


# -------------------------
# LOGIN
# -------------------------

@app.post("/login")

def login(form: OAuth2PasswordRequestForm = Depends()):

    if not verify_user(form.username, form.password):
        raise HTTPException(status_code=401, detail="Invalid login")

    token = create_token(form.username)

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# -------------------------
# CHAT
# -------------------------

@app.post("/chat")

def chat(data: ChatRequest, user_id: str = Depends(get_current_user)):

    message = data.message.strip()

    # -------------------------
    # MEMORY CAPTURE
    # -------------------------

    if message.lower().startswith("remember"):

        content = message.replace("remember", "").strip()

        if ":" in content:
            key, value = content.split(":", 1)

            save_user_memory(user_id, key.strip(), value.strip())

            return {"reply": "Got it. I'll remember that."}

    # -------------------------
    # LOAD MEMORY
    # -------------------------

    memory_context = load_user_memory(user_id)

    system_prompt = f"""
You are Shine Companion.

You remember important things about the user.

Known user facts:
{memory_context}

Use these memories when helping the user.
"""

    # -------------------------
    # OPENAI CALL
    # -------------------------

    response = client.chat.completions.create(
        model=SHINE_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    )

    reply = response.choices[0].message.content

    return {"reply": reply}