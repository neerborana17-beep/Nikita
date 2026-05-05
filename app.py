import os, requests, random, time, threading, re
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zayra_ai']

history_col = db['chat']
memory_col = db['memory']
event_col = db['events']

# -------- TIME --------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

# -------- MEMORY --------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text):

    mem = get_memory(chat_id)
    attach = mem.get("attachment", 20)

    # relationship progression (safe)
    if any(x in text.lower() for x in ["thank","nice","good"]):
        attach += 1

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "last_user": datetime.utcnow(),
            "attachment": max(0,min(100,attach))
        }},
        upsert=True
    )

# -------- MOOD ENGINE --------
def get_mood(chat_id):

    mem = get_memory(chat_id)
    attach = mem.get("attachment",20)

    if attach > 70:
        return "warm"
    elif attach < 20:
        return "neutral"
    return "friendly"

# -------- EVENT SYSTEM --------
def save_event(chat_id, text):

    match = re.search(r'(\d{1,2}) ?baje', text.lower())
    if not match:
        return False

    hour = int(match.group(1))
    t = now_ist().replace(hour=hour, minute=0, second=0)

    if t < now_ist():
        t += timedelta(days=1)

    event_col.insert_one({
        "chat_id": chat_id,
        "time": t,
        "msg": "aapne yaad dilane ko bola tha",
        "done": False
    })

    return True

def run_events(chat_id):
    now = now_ist()

    for e in event_col.find({"chat_id": chat_id, "done": False}):
        if now >= e["time"]:
            send(chat_id, e["msg"])
            event_col.update_one({"_id": e["_id"]}, {"$set": {"done": True}})

# -------- MEMORY GRAPH --------
def update_graph(chat_id, text):

    mem = get_memory(chat_id)
    graph = mem.get("graph", [])

    graph.append(text)

    if len(graph) > 5:
        graph.pop(0)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"graph": graph}},
        upsert=True
    )

# -------- CREATIVE --------
def creative(text):

    t = text.lower()

    if "shayari" in t:
        return random.choice([
            "aapki baatein yaad reh jaati hai",
            "dil ko sukoon aapse milta hai",
            "raat bhi thodi behtar lagti hai"
        ])

    if "joke" in t:
        return random.choice([
            "life bhi kabhi kabhi lag karti hai",
            "zyada socho mat system hang ho jayega"
        ])

    return None

# -------- LIGHT ROAST --------
def light_roast():

    return random.choice([
        "aap thode interesting ho waise",
        "kabhi kabhi aap confusing lagte ho",
        "aap ka style alag hai honestly"
    ])

# -------- PASSIVE TONE --------
def passive_line():

    return random.choice([
        "theek hai aap jaise comfortable ho",
        "aapka choice hai obviously",
        "main bas bol rahi thi"
    ])

# -------- SMART QUESTION --------
def smart_question():

    return random.choice([
        "aap kya karte ho normally",
        "aapko kya pasand hai",
        "free time me kya karte ho",
        "aapka day kaisa tha"
    ])

# -------- REAL TEXTING ENGINE --------
def typing(chat_id):
    requests.post(f"{TELEGRAM_API}/sendChatAction",
                  json={"chat_id": chat_id, "action": "typing"})
    time.sleep(random.uniform(1.5,3))

# -------- AI --------
def ai_reply(text, history, chat_id):

    context = ""
    for m in history:
        role = "User" if m["role"]=="user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    mood = get_mood(chat_id)

    prompt = f"""
You are Zayra.

- hinglish
- short replies (5-10 words)
- respectful tone
- use "aap"
- slightly playful
- sometimes ask questions
- mood: {mood}

CHAT:
{context}

User: {text}
"""

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model":"llama-3.3-70b-versatile",
            "messages":[{"role":"user","content":prompt}],
            "temperature":0.85,
            "max_tokens":60
        }
    )

    if r.status_code == 200:
        return r.json()['choices'][0]['message']['content']

    return "hmm"

# -------- AUTO MESSAGE --------
def auto_message(chat_id):

    mem = get_memory(chat_id)
    last = mem.get("auto")

    now = datetime.utcnow()

    if last and (now-last).total_seconds() < random.randint(3600,20000):
        return

    msg = random.choice([
        "kya kar rahe ho",
        smart_question(),
        "aaj ka din kaisa tha"
    ])

    typing(chat_id)
    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"auto": now}},
        upsert=True
    )

# -------- SEND --------
def send(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

# -------- AUTO LOOP --------
def loop():
    while True:
        time.sleep(random.randint(800,2000))
        auto_message(ALLOWED_USER_ID)
        run_events(ALLOWED_USER_ID)

# -------- WEBHOOK --------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    data = request.get_json()
    msg = data.get("message")

    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    if chat_id != ALLOWED_USER_ID:
        return {"ok": True}

    text = msg.get("text")
    if not text:
        return {"ok": True}

    update_memory(chat_id, text)
    update_graph(chat_id, text)

    if save_event(chat_id, text):
        send(chat_id, "ok yaad rahega")
        return {"ok": True}

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    reply = creative(text)

    if not reply:
        if random.random() < 0.1:
            reply = light_roast()

    if not reply:
        if random.random() < 0.1:
            reply = passive_line()

    if not reply:
        reply = ai_reply(text, history, chat_id)

    typing(chat_id)
    send(chat_id, reply)

    history_col.insert_one({
        "chat_id": chat_id,
        "role": "user",
        "content": text,
        "time": datetime.utcnow()
    })

    history_col.insert_one({
        "chat_id": chat_id,
        "role": "assistant",
        "content": reply,
        "time": datetime.utcnow()
    })

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Ultra Human AI Running"

threading.Thread(target=loop, daemon=True).start()
