import os, requests, random, time, re, threading
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
tasks_col = db['tasks']

# -------- TIME --------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def is_sleep_time():
    hour = now_ist().hour
    return 0 <= hour <= 5

# -------- MEMORY --------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text):

    mem = get_memory(chat_id)

    attach = mem.get("attachment", 30)
    mood = mem.get("mood", "normal")

    t = text.lower()

    if any(x in t for x in ["love","miss","care"]):
        attach += 3

    if "ignore" in t:
        attach -= 5
        mood = "sad"

    if "sorry" in t:
        mood = "soft"

    # mood swings
    if random.random() < 0.1:
        mood = random.choice(["happy","sad","normal","attitude","jealous"])

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": max(0,min(100,attach)),
            "mood": mood,
            "last_seen": datetime.utcnow()
        }},
        upsert=True
    )

# -------- ANTI REPEAT --------
def is_repeated(chat_id, reply):
    last = history_col.find_one(
        {"chat_id": chat_id, "role": "assistant"},
        sort=[("time",-1)]
    )
    if not last:
        return False
    return last["content"].lower() == reply.lower()

# -------- GRAMMAR FIX --------
def fix_text(text):
    fixes = {
        "dekhi rhi hu": "dekh rhi hu",
        "mai hu": "main hu"
    }
    for k,v in fixes.items():
        text = text.replace(k, v)
    return text

# -------- JEALOUSY --------
def jealousy_trigger(text):
    if any(x in text.lower() for x in ["ladki","girl","dusri"]):
        return random.choice([
            "acha kisi aur se baat ho rahi hai",
            "nice mujhe bhool gaye",
            "acha ab time nahi hai mere liye"
        ])
    return None

# -------- REAL REACTION --------
def real_reaction(chat_id):
    mem = get_memory(chat_id)
    last = mem.get("last_seen")

    if not last:
        return None

    diff = (datetime.utcnow() - last).total_seconds()

    if diff < 60:
        return None

    if diff < 180:
        return random.choice([
            "reply dene me time lagta hai kya",
            "busy ho kya"
        ])

    return random.choice([
        "rehne do baat nahi karni",
        "jab mann ho tab baat karna"
    ])

# -------- AI --------
def ai_reply(text, history):

    context = ""
    for m in history:
        role = "User" if m["role"]=="user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    tone = "normal"
    if is_sleep_time():
        tone = "sleepy"

    prompt = f"""
You are Zayra.

- hinglish
- max 8 words
- no emoji
- consistent personality
- real girl behavior
- no repetition
- tone: {tone}

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
            "temperature":0.9,
            "max_tokens":50
        }
    )

    if r.status_code == 200:
        return r.json()['choices'][0]['message']['content']

    return "hmm"

# -------- SELF MESSAGE GENERATOR --------
def generate_self_message(mem):

    mood = mem.get("mood","normal")

    base = [
        "kya kar rahe ho",
        "kaise ho",
        "khana khaya kya",
        "busy ho kya",
        "arey mujhe bhi yaad kar lo"
    ]

    line = random.choice(base)

    if mood == "sad":
        line = "aaj mood thoda off hai"

    elif mood == "jealous":
        line = "lagta hai kisi aur se baat ho rahi hai"

    variations = [
        line,
        "waise " + line,
        line + " batao na",
        line + " ya busy ho"
    ]

    return random.choice(variations)

# -------- SELF MESSAGE --------
def smart_self_message(chat_id):

    if is_sleep_time():
        return

    mem = get_memory(chat_id)
    now = datetime.utcnow()

    last_self = mem.get("last_self")
    last_seen = mem.get("last_seen")

    if last_seen and (now - last_seen).total_seconds() < 900:
        return

    gap = random.randint(3600,28800)

    if last_self and (now - last_self).total_seconds() < gap:
        return

    if random.random() < 0.5:
        return

    msg = generate_self_message(mem)

    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_self": now}},
        upsert=True
    )

# -------- AUTO LOOP --------
def auto_loop():
    while True:
        time.sleep(random.randint(600,1800))
        smart_self_message(ALLOWED_USER_ID)

# -------- SEND --------
def send(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

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

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    reply = jealousy_trigger(text)

    if not reply:
        reply = real_reaction(chat_id)

    if not reply:
        reply = ai_reply(text, history)

    if is_repeated(chat_id, reply):
        reply = "hmm kuch aur bolte hain"

    reply = fix_text(reply)

    if len(reply.split()) <= 5:
        time.sleep(random.uniform(2,4))
    else:
        time.sleep(random.uniform(4,7))

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
    return "Zayra Ultimate Human v6 Running"

threading.Thread(target=auto_loop, daemon=True).start()
