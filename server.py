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
# CONFIG
# ==============================

JWT_SECRET = os.getenv("JWT_SECRET", "shine-secret")
JWT_ALG = "HS256"
DB_PATH = "memory.db"

client = OpenAI()

app = FastAPI(title="Shine Companion")

security = HTTPBearer()


# ==============================
# LOAD USERS
# ==============================

def load_users():
    with open("users.json") as f:
        return json.load(f)

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

    username = data.username.lower()

    if username not in USERS:
        raise HTTPException(status_code=401, detail="Invalid user")

    if USERS[username] != data.password:
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

    memories = get_memory(user)
    context = "\n".join(memories)

    prompt = f"""
User memory:
{context}

User message:
{data.message}
"""

    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are Shine Companion."},
                {"role": "user", "content": prompt}
            ]
        )

        reply = response.choices[0].message.content

        if not reply:
            reply = "AI responded but returned empty text."

    except Exception as e:

        reply = f"AI error: {str(e)}"

    save_memory(user, data.message)

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

#loginBox{
padding:20px;
}

#chat{
flex:1;
overflow-y:auto;
padding:20px;
}

#inputBar{
display:flex;
gap:10px;
padding:20px;
background:#020617;
}

input{
padding:10px;
border-radius:6px;
border:none;
}

button{
padding:10px 20px;
background:#6366f1;
color:white;
border:none;
border-radius:6px;
}

</style>
</head>

<body>

<div id="loginBox">
<input id="u" placeholder="Username">
<input id="p" type="password" placeholder="Password">
<button onclick="login()">Login</button>
</div>

<div id="chat"></div>

<div id="inputBar">
<input id="msg" placeholder="Talk to Shine...">
<button onclick="send()">Send</button>
</div>

<script>

let token = ""

async function login(){

const res = await fetch("/login",{
method:"POST",
headers:{ "Content-Type":"application/json"},
body:JSON.stringify({
username:document.getElementById("u").value,
password:document.getElementById("p").value
})
})

const data = await res.json()

token=data.access_token

document.getElementById("chat").innerHTML += "<p><b>Shine:</b> Logged in.</p>"

}

async function send(){

let message=document.getElementById("msg").value

const res=await fetch("/chat",{
method:"POST",
headers:{
"Content-Type":"application/json",
"Authorization":"Bearer "+token
},
body:JSON.stringify({
message:message
})
})

const data=await res.json()

let chat=document.getElementById("chat")

chat.innerHTML += "<p><b>You:</b> "+message+"</p>"
chat.innerHTML += "<p><b>Shine:</b> "+(data.reply || "No response")+"</p>"

document.getElementById("msg").value=""

}

</script>

</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def ui():
    return UI