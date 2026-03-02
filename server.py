# =========================
# Shine Companion UI (inline)
# =========================
SHINE_UI_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Shine Companion</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial;margin:0;background:#0b0f17;color:#e7eefc}
    .wrap{max-width:820px;margin:0 auto;padding:22px}
    .card{background:#121a2a;border:1px solid #23304c;border-radius:16px;padding:18px;margin:14px 0}
    h1{margin:0 0 6px 0;font-size:28px}
    .sub{opacity:.8;margin-bottom:12px}
    input,button{font-size:16px;border-radius:12px;border:1px solid #2b3b5f;background:#0f1626;color:#e7eefc;padding:12px}
    input{width:100%;box-sizing:border-box;margin:8px 0}
    button{cursor:pointer}
    .row{display:flex;gap:10px;flex-wrap:wrap}
    .row > *{flex:1}
    #chat{white-space:pre-wrap}
    .msg{padding:10px 12px;border-radius:12px;margin:8px 0;border:1px solid #22314d;background:#0f1626}
    .you{border-color:#2c7be5}
    .shine{border-color:#6f42c1}
    .small{font-size:13px;opacity:.7}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Shine Companion</h1>
      <div class="sub">Login → Chat (JWT)</div>

      <div class="row">
        <div>
          <div class="small">Username</div>
          <input id="u" placeholder="doug" autocomplete="username" />
        </div>
        <div>
          <div class="small">Password</div>
          <input id="p" placeholder="••••••••" type="password" autocomplete="current-password" />
        </div>
      </div>
      <button onclick="login()">Login</button>
      <div id="loginStatus" class="small" style="margin-top:8px;"></div>
    </div>

    <div class="card">
      <div class="row">
        <input id="msg" placeholder="Say something..." onkeydown="if(event.key==='Enter'){sendMsg()}" />
        <button onclick="sendMsg()">Send</button>
      </div>
      <div id="chat"></div>
    </div>
  </div>

<script>
let token = null;

function bubble(cls, label, text){
  const chat = document.getElementById("chat");
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.innerHTML = "<b>" + label + ":</b> " + (text || "");
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function login(){
  const u = document.getElementById("u").value.trim();
  const p = document.getElementById("p").value;
  const st = document.getElementById("loginStatus");
  st.textContent = "Logging in...";
  try{
    const form = new URLSearchParams();
    form.append("username", u);
    form.append("password", p);

    const res = await fetch("/login", {
      method:"POST",
      headers:{"Content-Type":"application/x-www-form-urlencoded"},
      body: form.toString()
    });

    if(!res.ok){
      const t = await res.text();
      st.textContent = "Login failed: " + t;
      return;
    }
    const data = await res.json();
    token = data.access_token;
    st.textContent = "✅ Logged in";
    bubble("shine","Shine","Hello. You’re in. Say something.");
  }catch(e){
    st.textContent = "Login error: " + e;
  }
}

async function sendMsg(){
  const msgEl = document.getElementById("msg");
  const message = msgEl.value.trim();
  if(!message) return;
  if(!token){ alert("Login first"); return; }

  bubble("you","You",message);
  msgEl.value = "";

  const res = await fetch("/chat", {
    method:"POST",
    headers:{
      "Content-Type":"application/json",
      "Authorization":"Bearer " + token
    },
    body: JSON.stringify({message:message})
  });

  if(!res.ok){
    const t = await res.text();
    bubble("shine","Shine","Error: " + t);
    return;
  }
  const data = await res.json();
  bubble("shine","Shine", data.reply || "");
}
</script>
</body>
</html>
"""

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

def create_token(username: str):
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=12),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    return token
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return payload["sub"]
    except Exception:
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

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def shine_ui():

    return """
<!DOCTYPE html>
<html>
<head>

<title>Shine Companion</title>

<style>

body{
background:#0b1020;
color:white;
font-family:Arial;
text-align:center;

#chat{
width:650px;
height:420px;
border:1px solid #444;
margin:auto;
padding:15px;
overflow-y:auto;
border-radius:10px;

input{
width:420px;
padding:10px;
border-radius:6px;
border:none;

button{
padding:10px;
border:none;
background:#4e7cff;
color:white;
border-radius:6px;
cursor:pointer;

button:hover{
background:#6a91ff;

</style>

</head>

<body>

<h1>✨ Shine Companion</h1>

<div id="chat"></div>

<br>

<input id="msg" placeholder="Ask Shine something"/>
<button onclick="send()">Send</button>

<script>

let token=""

async function login(){

const res = await fetch("/login",{
method:"POST",
headers:{ "Content-Type":"application/json"},
body:JSON.stringify({
username:"doug",
password:"shine"
})
})

const data = await res.json()

token=data.access_token


async function send(){

const message=document.getElementById("msg").value

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

const chat=document.getElementById("chat")

chat.innerHTML += "<p><b>You:</b> "+message+"</p>"
chat.innerHTML += "<p><b>Shine:</b> "+data.reply+"</p>"

document.getElementById("msg").value=""


login()

</script>

</body>
</html>
"""
@app.get("/")
def shine_ui():
    return HTMLResponse("""
<!DOCTYPE html>
<html>
<head>
<title>Shine Companion</title>
<style>
body {
    background:#0b0f1a;
    color:white;
    font-family:Arial;
    text-align:center;
    padding:40px;
#chat {
    width:80%;
    height:400px;
    border:1px solid #333;
    margin:auto;
    overflow-y:auto;
    padding:10px;
input {
    width:60%;
    padding:10px;
button {
    padding:10px 20px;
</style>
</head>

<body>

<h1>✨ Shine Companion</h1>

<div id="chat"></div>

<br>

<input id="msg" placeholder="Talk to Shine..."/>
<button onclick="send()">Send</button>

<script>

let token = ""

async function login(){
    let form = new FormData()
    form.append("username","doug")
    form.append("password","shine")

    let res = await fetch("/login",{method:"POST",body:form})
    let data = await res.json()

    token = data.access_token

async function send(){

    let message = document.getElementById("msg").value

    let res = await fetch("/chat",{
        method:"POST",
        headers:{
            "Content-Type":"application/json",
            "Authorization":"Bearer "+token
        },
        body:JSON.stringify({message:message})
    })

    let data = await res.json()

    let chat = document.getElementById("chat")

    chat.innerHTML += "<p><b>You:</b> "+message+"</p>"
    chat.innerHTML += "<p><b>Shine:</b> "+data.reply+"</p>"

    document.getElementById("msg").value=""

login()

</script>

</body>
</html>
""")

@app.get("/")
def ui():
    return HTMLResponse("""
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

#chat{
flex:1;
overflow-y:auto;
padding:20px;

input{
width:80%;
padding:10px;
border-radius:6px;
border:none;

button{
padding:10px 20px;
background:#6366f1;
color:white;
border:none;
border-radius:6px;

#inputBar{
display:flex;
gap:10px;
padding:20px;
background:#020617;
</style>
</head>

<body>

<div id="chat"></div>

<div id="inputBar">
<input id="msg" placeholder="Talk to Shine...">
<button onclick="send()">Send</button>
</div>

<script>

let token = ""

async function login(){

let form = new FormData()
form.append("username","doug")
form.append("password","shine")

let res = await fetch("/login",{method:"POST",body:form})
let data = await res.json()

token = data.access_token


async function send(){

let message = document.getElementById("msg").value

let res = await fetch("/chat",{
method:"POST",
headers:{
"Content-Type":"application/json",
"Authorization":"Bearer "+token
},
body:JSON.stringify({message:message})
})

let data = await res.json()

let chat = document.getElementById("chat")

chat.innerHTML += "<p><b>You:</b> "+message+"</p>"
chat.innerHTML += "<p><b>Shine:</b> "+data.reply+"</p>"

document.getElementById("msg").value=""


login()

</script>

</body>
</html>
""")




@app.get("/", response_class=HTMLResponse)
def root_ui():
    return SHINE_UI_HTML

@app.get("/ui", response_class=HTMLResponse)
def ui_alias():
    return SHINE_UI_HTML



