# app.py

import os
import requests
import random
import time
import threading
import re
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime
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

def get_day_context():
    h = now_ist().hour
    return (
        "morning" if 5 <= h < 12 else
        "afternoon" if 12 <= h < 17 else
        "evening" if 17 <= h < 22 else
        "night"
    )

def is_night():
    h = now_ist().hour
    return h >= 22 or h < 5

# ---------- USER PROFILE ----------
def ensure_user_profile(chat_id):
    memory_col.update_one(
        {"chat_id": chat_id},
        {"$setOnInsert": {
            "name": "Chandra Prakash",
            "nickname": "cp",
            "location": "Nagaur",
            "work": "student"
        }},
        upsert=True
    )

# ---------- TELEGRAM ----------
def human_delay(text, mood="normal"):
    base = len(text) * 0.04
    mood_mult = {"normal": 1, "romantic": 1.2, "jealous": 1.1, "sleepy": 1.6}.get(mood, 1)
    return min(max(base * mood_mult, 1.2), 6)

def typing(chat_id, text="", mood="normal"):
    try:
        requests.post(f"{TELEGRAM_API}/sendChatAction",
                      json={"chat_id": chat_id, "action": "typing"}, timeout=5)
        time.sleep(human_delay(text, mood))
    except:
        pass

def send(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=5)
    except:
        pass

# ---------- MEMORY ----------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text=""):
    update = {"last_seen": datetime.utcnow()}
    if text:
        update["last_msg"] = text
    memory_col.update_one({"chat_id": chat_id}, {"$set": update}, upsert=True)

def dynamic_learning(chat_id, text):
    t = text.lower()

    # learn exam
    if "exam" in t:
        memory_col.update_one(
            {"chat_id": chat_id},
            {"$set": {"exam": True}},
            upsert=True
        )

    # learn study habit
    if "study" in t:
        memory_col.update_one(
            {"chat_id": chat_id},
            {"$set": {"studying": True}},
            upsert=True
        )

def update_personality(chat_id, text):
    t = text.lower()
    update = {}

    if "pasand" in t or "like" in t:
        update["likes"] = text

    if any(x in t for x in ["ladki", "gf", "bf", "friend"]):
        update["jealous_trigger"] = True

    if update:
        memory_col.update_one({"chat_id": chat_id}, {"$set": update}, upsert=True)

# ---------- MERGE ----------
def merge(chat_id, text):
    last = history_col.find_one(
        {"chat_id": chat_id, "role": "user"},
        sort=[("time", -1)]
    )
    if not last:
        return text

    if len(text) < 50 and (datetime.utcnow() - last["time"]).total_seconds() < 10:
        return f"{last['content']} {text}"

    return text

# ---------- LOCATION MOOD ----------
def location_context(mem):
    if mem.get("location") == "Nagaur":
        return random.choice([
            "waha garmi hoti hai na 😅",
            "Nagaur me aaj mausam kesa hai?",
            "bahar gaye the ya ghar pe the?"
        ])
    return ""

# ---------- SMART QUESTION ----------
def smart_question(chat_id, text):
    mem = get_memory(chat_id)

    if mem.get("exam"):
        return random.choice([
            "exam ki tayari kaisi chal rahi hai?",
            "padhai ho rahi hai na cp?"
        ])

    return random.choice([
        "aaj din kesa tha?",
        "kuch khaya aapne?",
        "thak gaye kya?"
    ])

# ---------- EMOTION ----------
def emotion_layer(text, mem):
    if is_night():
        return "sleepy"
    if mem.get("jealous_trigger"):
        return "jealous"
    return "normal"

# ---------- AI ----------
def ai(text, history, chat_id):
    mem = get_memory(chat_id)
    mood = emotion_layer(text, mem)

    profile = {
        "name": mem.get("name", "Chandra Prakash"),
        "nickname": mem.get("nickname", "cp"),
        "location": mem.get("location", "Nagaur"),
        "work": mem.get("work", "student")
    }

    context = "\n".join(
        f"{'User' if m['role']=='user' else 'Zayra'}: {m['content']}"
        for m in history
    )

    personality = f"""
- you are a real girl
- call user {profile['nickname']}
- user is a {profile['work']} from {profile['location']}
- VERY SHORT replies
- casual hinglish
- sometimes ask about study/life
"""

    if mood == "sleepy":
        personality += "\n- sleepy tone"

    prompt = f"""
You are Zayra.

{personality}

Chat:
{context}

User: {text}
"""

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 50
            },
            timeout=8
        )

        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"].strip().split("\n")[0]

            # smart add-ons
            if random.random() < 0.4:
                reply += " " + smart_question(chat_id, text)

            if random.random() < 0.3:
                loc = location_context(mem)
                if loc:
                    reply += " " + loc

            return reply[:80]

    except:
        pass

    return "hmm..."

# ---------- DELAY ----------
def maybe_delay_reply():
    if is_night() and random.random() < 0.3:
        time.sleep(random.randint(5, 20))

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
    update_personality(chat_id, text)
    dynamic_learning(chat_id, text)

    merged = merge(chat_id, text)

    history = list(
        history_col.find({"chat_id": chat_id})
        .sort("time", -1)
        .limit(10)
    )
    history.reverse()

    reply = ai(merged, history, chat_id)

    mood = emotion_layer(text, get_memory(chat_id))

    maybe_delay_reply()
    typing(chat_id, reply, mood)
    send(chat_id, reply)

    now = datetime.utcnow()

    history_col.insert_many([
        {"chat_id": chat_id, "role": "user", "content": merged, "time": now},
        {"chat_id": chat_id, "role": "assistant", "content": reply, "time": now}
    ])

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra AI Running"

threading.Thread(target=lambda: None, daemon=True).start()
