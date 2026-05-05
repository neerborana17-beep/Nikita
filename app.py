import os
import requests
import random
import time
import threading
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

# ---------- TELEGRAM ----------
def human_delay(text, mood="normal"):
    base = len(text) * 0.04
    mood_mult = {
        "normal": 1,
        "romantic": 1.2,
        "jealous": 1.1,
        "sleepy": 1.6
    }.get(mood, 1)

    return min(max(base * mood_mult, 1.2), 6)

def typing(chat_id, text="", mood="normal"):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"},
            timeout=5
        )
        time.sleep(human_delay(text, mood))
    except:
        pass

def send(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5
        )
    except:
        pass

# ---------- MEMORY ----------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id):
    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_seen": datetime.utcnow()}},
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
        memory_col.update_one(
            {"chat_id": chat_id},
            {"$set": update},
            upsert=True
        )

# ---------- MERGE ----------
def merge(chat_id, text):
    last = history_col.find_one(
        {"chat_id": chat_id, "role": "user"},
        sort=[("time", -1)]
    )

    if not last:
        return text

    if (
        len(text) < 50 and
        (datetime.utcnow() - last["time"]).total_seconds() < 10
    ):
        return f"{last['content']} {text}"

    return text

# ---------- EMOTION ----------
def emotion_layer(text, mem):
    t = text.lower()

    if is_night():
        return "sleepy"

    if mem.get("jealous_trigger") or any(x in t for x in ["kisi aur", "dusri"]):
        return "jealous"

    if any(x in t for x in ["miss", "yaad", "love"]):
        return "romantic"

    return "normal"

# ---------- AI ----------
def ai(text, history, chat_id):
    context = "\n".join(
        f"{'User' if m['role']=='user' else 'Zayra'}: {m['content']}"
        for m in history
    )

    mem = get_memory(chat_id)
    mood = emotion_layer(text, mem)

    # ---- SHORT USER DETECTION ----
    short_inputs = ["hmm", "acha", "ok", "k", "kyu", "kyu?", "kese", "kisliye", "hmm...", "achha", "haan"]
    if text.lower().strip() in short_inputs:
        return random.choice([
            "hmm... kya soch rahe ho?",
            "acha ji ",
            "tum bhi na",
            "kyu? kuch hua kya?",
            "itna short reply ",
            "batao na properly"
        ])

    # ---- PERSONALITY ----
    personality = """
- real human texting style
- hinglish casual
- VERY SHORT replies (max 1 sentence)
- sometimes 2 short lines max
- no long paragraphs EVER
- use fillers like: hmm, acha, tum bhi na, arey, suno
- slightly flirty, emotional
- natural typing style (not perfect grammar)
- don't explain too much
- sometimes tease
"""

    if mood == "jealous":
        personality += "\n- slightly jealous, like 'kisi aur se baat kar rahe ho?'"
    elif mood == "romantic":
        personality += "\n- soft, caring, little clingy"
    elif mood == "sleepy":
        personality += "\n- sleepy, low energy, very short replies like 'hmm sone do na...'"

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
                "temperature": 0.85,
                "max_tokens": 60
            },
            timeout=8
        )

        if r.status_code == 200:
            reply = r.json()["choices"][0]["message"]["content"]

            # ---- HARD SHORTEN ----
            reply = reply.strip().split("\n")[0]  # keep first line only

            # cut long sentences
            if len(reply) > 80:
                reply = reply[:80]

            return reply

    except:
        pass

    return random.choice([
        "hmm...",
        "acha...",
        "tum bhi na",
        "kya hua?"
    ])

# ---------- REALISTIC DELAY ----------
def maybe_delay_reply():
    if is_night():
        # 30% chance delay
        if random.random() < 0.3:
            time.sleep(random.randint(5, 20))

# ---------- AUTO ----------
def auto():
    while True:
        time.sleep(random.randint(1500, 3500))
        if ALLOWED_USER_ID:
            self_msg(ALLOWED_USER_ID)

def self_msg(chat_id):
    mem = get_memory(chat_id)
    last = mem.get("self_time")

    if last and (datetime.utcnow() - last).total_seconds() < 3600:
        return

    if is_night():
        msg = random.choice([
            "so gaye kya...?",
            "good night bolke jao na...",
            "neend aa rahi hai... aap?"
        ])
    else:
        msg = random.choice([
            "kya kar rahe ho",
            "miss kar rahi thi...",
            "busy ho kya"
        ])

    typing(chat_id, msg, "sleepy" if is_night() else "normal")
    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"self_time": datetime.utcnow()}},
        upsert=True
    )

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

    update_memory(chat_id)
    update_personality(chat_id, text)

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

# ---------- THREAD ----------
threading.Thread(target=auto, daemon=True).start()
