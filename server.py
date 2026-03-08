import os
import json
import sqlite3
import jwt
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from openai import OpenAI

# ==============================
# LOAD DOUG BRAIN FILES
# ==============================

import json
import os

MEMORY_PATH = "memory"

C_BRAIN = {}

def load_brain():

    global C_BRAIN

    brain = {}

    if os.path.exists(MEMORY_PATH):

        for file in os.listdir(MEMORY_PATH):

            if file.endswith(".json"):

                path = os.path.join(MEMORY_PATH, file)

                try:

                    with open(path,"r",encoding="utf-8") as f:

                        data=json.load(f)

                        brain[file]=data

                except Exception as e:

                    print("Brain load error:",file,e)

    C_BRAIN = brain

    print("🧠 C brain loaded.")
    print("Memory files:", list(brain.keys()))

load_brain()

# ==============================
# CONFIG
# ==============================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JWT_SECRET = os.getenv("JWT_SECRET", "shine-secret")
JWT_ALG = "HS256"
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "memory.db"))
USERS_PATH = os.getenv("USERS_PATH", os.path.join(BASE_DIR, "users.json"))

client = OpenAI()  # expects OPENAI_API_KEY env var on Railway
app = FastAPI(title="Shine Companion")
security = HTTPBearer()


# ==============================
# LOAD USERS
# ==============================

def load_users():
    try:
        with open(USERS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # ✅ normalize keys so "Doug" and "doug" both work
        return {str(k).lower(): str(v) for k, v in raw.items()}
    except FileNotFoundError:
        # Clear error so Railway logs show it immediately
        raise RuntimeError(f"users.json not found at: {USERS_PATH}")
    except Exception as e:
        raise RuntimeError(f"Failed to load users.json: {e}")

USERS = load_users()


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

def create_token(username: str):
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
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ==============================
# LOGIN
# ==============================

@app.post("/login")
def login(data: LoginRequest):
    username = (data.username or "").strip().lower()
    password = data.password or ""

    if not username:
        raise HTTPException(status_code=400, detail="Missing username")

    if username not in USERS:
        raise HTTPException(status_code=401, detail="Invalid user")

    if USERS[username] != password:
        raise HTTPException(status_code=401, detail="Invalid password")

    token = create_token(username)
    return {"access_token": token}


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
    message = (data.message or "").strip()
    if not message:
        return {"reply": "Say something and hit send 🙂"}

    memories = get_memory(user)
    context = "\n".join(memories)

    prompt = f"""
User memory:
{context}

User message:
{message}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Shine Companion."},
                {"role": "user", "content": prompt}
            ]
        )
        reply = response.choices[0].message.content or "AI responded but returned empty text."
    except Exception as e:
        reply = f"AI error: {str(e)}"

    # save the user message (simple v1)
    save_memory(user, message)

    return {"reply": reply}


# ==============================
# UI
# ==============================

UI = """
<!DOCTYPE html>
<html>
<head>
<title>Shine Companion</title>
<style>
body{
  background:#0f172a;
  color:white;
  font-family:Arial;
  display:flex;
  flex-direction:column;
  height:100vh;
  margin:0;
}
#loginBox{ padding:20px; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
#chat{ flex:1; overflow-y:auto; padding:20px; }
#inputBar{ display:flex; gap:10px; padding:20px; background:#020617; }
input{ padding:10px; border-radius:6px; border:none; }
button{ padding:10px 20px; background:#6366f1; color:white; border:none; border-radius:6px; cursor:pointer; }
.small{ opacity:.8; font-size:13px; }
</style>
</head>

<body>
<div id="loginBox">
  <input id="u" placeholder="Username" autocomplete="username">
  <input id="p" type="password" placeholder="Password" autocomplete="current-password">
  <button onclick="login()">Login</button>
  <span id="status" class="small"></span>
</div>

<div id="chat"></div>

<div id="inputBar">
  <input id="msg" placeholder="Talk to Shine..." style="flex:1">
  <button onclick="send()">Send</button>
</div>

<script>
let token = "";

function addLine(who, text){
  const chat = document.getElementById("chat");
  chat.innerHTML += `<p><b>${who}:</b> ${text}</p>`;
  chat.scrollTop = chat.scrollHeight;
}

document.getElementById("msg").addEventListener("keydown", (e) => {
  if(e.key === "Enter") send();
});

async function login(){
  const status = document.getElementById("status");
  status.textContent = "Logging in...";

  const username = document.getElementById("u").value;
  const password = document.getElementById("p").value;

  const res = await fetch("/login",{
    method:"POST",
    headers:{ "Content-Type":"application/json"},
    body: JSON.stringify({ username, password })
  });

  let data = null;
  try { data = await res.json(); } catch(e) {}

  if(!res.ok){
    const detail = (data && (data.detail || data.message)) ? (data.detail || data.message) : ("HTTP " + res.status);
    status.textContent = "❌ " + detail;
    addLine("Shine", "Login failed: " + detail);
    return;
  }

  token = data.access_token;
  status.textContent = "✅ Logged in";
  addLine("Shine", "Logged in. Say something.");
}

async function send(){
  const msgEl = document.getElementById("msg");
  const message = msgEl.value.trim();
  if(!message) return;

  if(!token){
    addLine("Shine", "Login first 🙂");
    return;
  }

  addLine("You", message);
  msgEl.value = "";

  const res = await fetch("/chat",{
    method:"POST",
    headers:{
      "Content-Type":"application/json",
      "Authorization":"Bearer " + token
    },
    body: JSON.stringify({ message })
  });

  let data = null;
  try { data = await res.json(); } catch(e) {}

  if(!res.ok){
    const detail = (data && (data.detail || data.message)) ? (data.detail || data.message) : ("HTTP " + res.status);
    addLine("Shine", "Error: " + detail);
    return;
  }

  addLine("Shine", (data.reply || "No response"));
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def ui():
    return UI
