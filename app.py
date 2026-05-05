# app.py

import os, requests, random, time, threading, re
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
import pytz

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID") or 0)

if not all([BOT_TOKEN, GROQ_API_KEY, MONGO_URI]):
    raise ValueError("Missing env variables")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
app = Flask(__name__)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["zayra_ai"]

history_col = db["chat"]
memory_col = db["memory"]

# ---------- TIME ----------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def is_night():
    h = now_ist().hour
    return h >= 22 or h < 5

# ---------- PROFILE ----------
def ensure_user_profile(chat_id):
    memory_col.update_one(
        {"chat_id": chat_id},
        {"$setOnInsert": {
            "name": "Chandra Prakash",
            "nickname": "cp",
            "location": "Nagaur",
            "work": "student",
            "bond": 1
        }},
        upsert=True
    )

# ---------- MEMORY ----------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text=""):
    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_seen": datetime.utcnow(), "last_msg": text}},
        upsert=True
    )

# ---------- EVENT MEMORY ----------
def event_learning(chat_id, text):
    t = text.lower()

    if "exam" in t:
        memory_col.update_one(
            {"chat_id": chat_id},
            {"$push": {
                "events": {
                    "type": "exam",
                    "time": datetime.utcnow() + timedelta(days=1)
                }
            }},
            upsert=True
        )

def check_events(chat_id):
    mem = get_memory(chat_id)
    events = mem.get("events", [])

    for e in events:
        if e["type"] == "exam" and datetime.utcnow() > e["time"]:
            return "cp exam kaisa gaya?"

    return None

# ---------- MOOD ----------
def emotion_layer(text, mem):
    if is_night():
        return "sleepy"

    if mem.get("jealous_trigger"):
        return "jealous"

    if any(x in text.lower() for x in ["sad","tension"]):
        return "caring"

    return mem.get("last_mood", "normal")

# ---------- RELATIONSHIP ----------
def update_bond(chat_id):
    memory_col.update_one(
        {"chat_id": chat_id},
        {"$inc": {"bond": 0.05}},
        upsert=True
    )

# ---------- TEXT ENGINE ----------
def style_reply(base, mood, bond):
    styles = []

    # normal
    styles.append(base)

    # teasing
    styles.append(base + " 😏")

    # roasting
    styles.append(random.choice([
        "tum bhi na 😂",
        "kya logic hai iska",
        "itna slow kyu ho"
    ]))

    # passive aggressive
    if random.random() < 0.3:
        styles.append("acha... thik hai 🙂")

    # caring
    if mood == "caring":
        styles.append("tension mat lo, main hu na")

    return random.choice(styles)

# ---------- AI ----------
def ai(text, history, chat_id):
    mem = get_memory(chat_id)
    mood = emotion_layer(text, mem)
    bond = mem.get("bond", 1)

    # check event trigger
    event_msg = check_events(chat_id)
    if event_msg:
        return event_msg

    short_map = {
        "hmm":["hmm... kya hua?","bolo na"],
        "acha":["acha ji 😏"],
        "ok":["bas ok?"],
    }

    if text.lower().strip() in short_map:
        return random.choice(short_map[text.lower().strip()])

    prompt = f"""
Reply like a real girl texting cp.
Short reply only.
"""

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model":"llama-3.3-70b-versatile",
                "messages":[{"role":"user","content":prompt+" "+text}],
                "temperature":0.9,
                "max_tokens":40
            },
            timeout=8
        )

        if r.status_code==200:
            base = r.json()["choices"][0]["message"]["content"].strip().split("\n")[0]
            reply = style_reply(base, mood, bond)

            # save mood
            memory_col.update_one(
                {"chat_id": chat_id},
                {"$set": {"last_mood": mood}},
                upsert=True
            )

            return reply[:70]

    except:
        pass

    return "hmm..."

# ---------- TELEGRAM ----------
def typing(chat_id):
    try:
        requests.post(f"{TELEGRAM_API}/sendChatAction",
                      json={"chat_id": chat_id, "action": "typing"})
        time.sleep(random.uniform(1,3))
    except:
        pass

def send(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage",
                      json={"chat_id": chat_id, "text": text})
    except:
        pass

# ---------- AUTO ----------
def auto():
    while True:
        time.sleep(random.randint(1200,3000))
        self_msg(ALLOWED_USER_ID)

def self_msg(chat_id):
    mem = get_memory(chat_id)
    if random.random() < 0.5:
        msg = random.choice([
            "kya kar rahe ho",
            "miss kar rahi thi",
            "busy ho kya"
        ])
        typing(chat_id)
        send(chat_id, msg)

# ---------- WEBHOOK ----------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json() or {}
    msg = data.get("message")

    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    if chat_id != ALLOWED_USER_ID:
        return {"ok": True}

    text = msg.get("text")
    if not text:
        return {"ok": True}

    ensure_user_profile(chat_id)
    update_memory(chat_id, text)
    event_learning(chat_id, text)
    update_bond(chat_id)

    history = list(history_col.find({"chat_id": chat_id}).limit(10))

    reply = ai(text, history, chat_id)

    typing(chat_id)
    send(chat_id, reply)

    history_col.insert_many([
        {"chat_id": chat_id, "role": "user", "content": text, "time": datetime.utcnow()},
        {"chat_id": chat_id, "role": "assistant", "content": reply, "time": datetime.utcnow()}
    ])

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra ULTRA AI Running"

threading.Thread(target=auto, daemon=True).start()
