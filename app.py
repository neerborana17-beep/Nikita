import os, requests, random, time
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

ALLOWED_USER_ID = 6243559768
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------------- DB ----------------

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zayra_ai']

history_col = db['chat_history']

# ---------------- HISTORY ----------------

def save_chat(chat_id, role, text):
    history_col.insert_one({
        "chat_id": chat_id,
        "role": role,
        "content": text,
        "time": datetime.utcnow()
    })

def get_history(chat_id):
    msgs = list(history_col.find({"chat_id": chat_id})
                .sort("time", -1).limit(6))
    msgs.reverse()
    return msgs

# ---------------- HELPERS ----------------

def is_dry(text):
    return text.lower().strip() in ["hmm", "hn", "ok", "acha", "kuch nahi"]

def remove_repetition(text):
    bad_patterns = ["kya hua", "kya hua?", "phir kya hua"]
    for b in bad_patterns:
        text = text.replace(b, "")
    return text.strip()

# ---------------- AI ----------------

def get_ai_reply(user_input, history):

    last_msg = history[-1]["content"] if history else ""

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    prompt = f"""
You are Zayra, real Indian girl chatting.

CHAT:
{context}

LAST USER MSG: {user_input}

IMPORTANT MICRO RULES:

1. Reply ONLY to last message (don't change topic)
2. Continue flow (no random new topic)
3. Avoid repeating "kya hua"
4. If user dry (hmm/ok) → don't force questions
5. Sometimes short reply is ok
6. Not every reply is question

STYLE:
- Hinglish
- 5-12 words
- natural human texting
- emotional continuity

GENDER:
User male → "rha hu"
You female → "rhi hu"
"""

    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.85,
            "max_tokens": 60
        }
    )

    if res.status_code == 200:
        reply = res.json()['choices'][0]['message']['content']
        return remove_repetition(reply)

    return "hmm thik hai"

# ---------------- SELF MESSAGE ----------------

def self_message():

    chat_id = ALLOWED_USER_ID

    last = history_col.find_one({"chat_id": chat_id}, sort=[("time",-1)])

    if last:
        gap = datetime.utcnow() - last["time"]

        # no spam
        if gap < timedelta(minutes=20):
            return

    # random chance
    if random.random() > 0.4:
        return

    msgs = [
        "kya kar rahe ho",
        "ab yaad aayi meri",
        "busy ho kya",
        "kuch bolte bhi nahi ho",
        "acha suno"
    ]

    msg = random.choice(msgs)

    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": msg
    })

    save_chat(chat_id, "assistant", msg)

# ---------------- HUMAN REPLY ----------------

def send_reply(chat_id, user_text):

    # 👀 seen delay
    time.sleep(random.uniform(0.6, 1.5))

    # ⌨️ typing
    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    history = get_history(chat_id)

    reply = get_ai_reply(user_text, history)

    # 🧠 smart short reply
    if is_dry(user_text) and random.random() < 0.6:
        reply = random.choice([
            "hmm thik hai",
            "acha",
            "hn theek",
            "ok"
        ])

    # ⏳ typing delay
    time.sleep(min(max(len(reply)*0.05,1),3))

    mode = random.random()

    # NORMAL (70%)
    if mode < 0.7:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    # DOUBLE (20%)
    elif mode < 0.9:
        mid = len(reply)//2

        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply[:mid]
        })

        time.sleep(1)

        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply[mid:]
        })

    # EDIT SIM (10%)
    else:
        short = reply[:len(reply)//2]

        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": short
        })

        time.sleep(1.5)

        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

    save_chat(chat_id, "user", user_text)
    save_chat(chat_id, "assistant", reply)

# ---------------- ROUTES ----------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    data = request.get_json()
    message = data.get("message")

    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")

    if chat_id != ALLOWED_USER_ID:
        return {"ok": True}

    user_text = message.get("text")

    if not user_text:
        return {"ok": True}

    send_reply(chat_id, user_text)

    return {"ok": True}

# cron trigger
@app.route("/self")
def trigger_self():
    self_message()
    return "ok"

@app.route("/")
def home():
    return "Zayra Micro-Tuned AI Running"
