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

# -------- TIME --------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

# -------- MEMORY --------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text):
    mem = get_memory(chat_id)

    attach = mem.get("attachment", 30)
    mood = mem.get("mood", "normal")
    mood_lock = mem.get("mood_lock", 0)

    t = text.lower()

    if mood_lock <= 0:
        if "love" in t or "miss" in t:
            mood = "happy"
            attach += 3
            mood_lock = 3
        elif "ignore" in t:
            mood = "sad"
            attach -= 3
            mood_lock = 3
    else:
        mood_lock -= 1

    attach = max(0, min(100, attach))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": attach,
            "mood": mood,
            "mood_lock": mood_lock
        }},
        upsert=True
    )

# -------- THINKING LAYER --------
def thinking_layer(user_text, history, mem):

    last_user = user_text.lower()
    last_bot = ""

    for m in reversed(history):
        if m["role"] == "assistant":
            last_bot = m["content"].lower()
            break

    # context consistency
    if "gussa" in last_bot:
        return random.choice([
            "abhi bhi gussa hu",
            "itni jaldi thik nahi hota 😒"
        ])

    # question follow-up
    if "?" in last_user:
        return None

    return None

# -------- EMOTION ENGINE --------
def emotion_engine(mem):

    mood = mem.get("mood", "normal")
    attach = mem.get("attachment", 30)

    if mood == "sad":
        return random.choice([
            "acha thik",
            "jo tumhe sahi lage"
        ])

    if attach > 70:
        return random.choice([
            "tumse baat acchi lagti h",
            "tum special ho 🙂"
        ])

    return None

# -------- AI --------
def ai_reply(user_text, history):

    context = ""
    for m in history:
        role = "User" if m["role"]=="user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    prompt = f"""
You are Zayra (real indian girl)

RULES:
- hinglish
- max 8 words
- natural texting
- no robotic reply
- emotional continuity
- behave like real girl

CHAT:
{context}

User: {user_text}
"""

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model":"llama-3.3-70b-versatile",
            "messages":[{"role":"user","content":prompt}],
            "temperature":0.85,
            "max_tokens":50
        }
    )

    if r.status_code == 200:
        return r.json()['choices'][0]['message']['content']

    return "hmm"

# -------- CONTROL --------
def control(reply):
    words = reply.split()
    if len(words) > 8:
        reply = " ".join(words[:6])
    return reply

# -------- GRAMMAR FIX --------
def fix_grammar(r):

    fixes = {
        "gussa hai mujhe": "mujhe gussa hai",
        "acha lagta hai mujhe": "mujhe acha lagta hai"
    }

    for w, c in fixes.items():
        r = r.replace(w, c)

    return r

# -------- HUMAN DELAY --------
def human_delay(chat_id, reply):

    words = len(reply.split())

    time.sleep(random.uniform(0.5,1.5))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    if words <= 5:
        time.sleep(random.uniform(2,4))
    else:
        time.sleep(random.uniform(4,7))

# -------- PROACTIVE --------
def proactive(chat_id):

    if random.random() > 0.3:
        return

    msg = random.choice([
        "acha suno ek baat",
        "tum free ho?",
        "kya soch rahe ho?"
    ])

    time.sleep(random.uniform(2,4))
    send(chat_id, msg)

# -------- AUTO MESSAGE --------
def auto_loop():
    while True:
        time.sleep(300)

        if random.random() < 0.4:
            send(ALLOWED_USER_ID, random.choice([
                "kya kar rahe ho",
                "yaad aa rahe ho",
                "reply nahi karte 😒"
            ]))

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

    mem = get_memory(chat_id)

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time", -1).limit(10))
    history.reverse()

    # -------- BRAIN PIPELINE --------
    reply = thinking_layer(text, history, mem)

    if not reply:
        reply = emotion_engine(mem)

    if not reply:
        reply = ai_reply(text, history)

    reply = control(reply)
    reply = fix_grammar(reply)

    human_delay(chat_id, reply)
    send(chat_id, reply)

    proactive(chat_id)

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

    update_memory(chat_id, text)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Brain v2 Pro Running 🔥"

# start auto messaging
threading.Thread(target=auto_loop, daemon=True).start()
