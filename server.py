import os
import sqlite3
import jwt
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from openai import OpenAI

app = FastAPI(title="Shine Companion")

# ==============================
# CONFIG
# ==============================

JWT_SECRET = os.getenv("JWT_SECRET", "shine-secret")
JWT_ALG = "HS256"
DB_PATH = "memory.db"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

security = HTTPBearer()

# ==============================
# DATABASE
# ==============================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        content TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ==============================
# MODELS
# ==============================

class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str


# ==============================
# AUTH
# ==============================

def create_token(username):

    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=12)
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):

    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload["sub"]

    except:
        raise HTTPException(status_code=401, detail="Invalid token")


# ==============================
# ROOT (STATUS PAGE)
# ==============================

@app.get("/")
def root():
    return {
        "status": "Shine Companion Core Online",
        "version": "0.1",
        "time": datetime.utcnow()
    }


# ==============================
# LOGIN
# ==============================

@app.post("/login")
def login(data: LoginRequest):

    # temporary simple login
    if data.username == "doug" and data.password == "shine":
        token = create_token(data.username)
        return {"token": token}

    raise HTTPException(status_code=401, detail="Invalid credentials")


# ==============================
# MEMORY
# ==============================

def save_memory(user, content):

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "INSERT INTO memory (user, content, created_at) VALUES (?, ?, ?)",
        (user, content, datetime.utcnow().isoformat())
    )

    conn.commit()
    conn.close()


def get_memory(user):

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT content FROM memory WHERE user=? ORDER BY id DESC LIMIT 5",
        (user,)
    )

    rows = c.fetchall()
    conn.close()

    return [r[0] for r in rows]


# ==============================
# CHAT
# ==============================

@app.post("/chat")
def chat(data: ChatRequest, user=Depends(verify_token)):

    memories = get_memory(user)

    context = "\n".join(memories)

    prompt = f"""
User memory:
{context}

User message:
{data.message}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are Shine Companion."},
            {"role": "user", "content": prompt}
        ]
    )

    reply = response.choices[0].message.content

    save_memory(user, data.message)

    return {"reply": reply}
