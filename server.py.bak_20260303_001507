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
}

#chat{
width:650px;
height:420px;
border:1px solid #444;
margin:auto;
padding:15px;
overflow-y:auto;
border-radius:10px;
}

input{
width:420px;
padding:10px;
border-radius:6px;
border:none;
}

button{
padding:10px;
border:none;
background:#4e7cff;
color:white;
border-radius:6px;
cursor:pointer;
}

button:hover{
background:#6a91ff;
}

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

}

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

}

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
}
#chat {
    width:80%;
    height:400px;
    border:1px solid #333;
    margin:auto;
    overflow-y:auto;
    padding:10px;
}
input {
    width:60%;
    padding:10px;
}
button {
    padding:10px 20px;
}
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
}

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
}

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
}

#chat{
flex:1;
overflow-y:auto;
padding:20px;
}

input{
width:80%;
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

#inputBar{
display:flex;
gap:10px;
padding:20px;
background:#020617;
}
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

}

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

}

login()

</script>

</body>
</html>
""")


