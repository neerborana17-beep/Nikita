import os, requests, random
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

ALLOWED_USER_ID = 6243559768
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------------- DB ----------------

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zayra_ai']

memory_col = db['user_memory']
history_col = db['chat_history']

# ---------------- HISTORY ----------------

def save_chat(chat_id, role, text):
    history_col.insert_one({
        "chat_id": chat_id,
        "role": role,
        "content": text,
        "time": datetime.utcnow()
    })

def get_last_time(chat_id):
    msg = history_col.find_one({"chat_id": chat_id}, sort=[("time",-1)])
    return msg["time"] if msg else None

# ---------------- EVOLUTION ENGINE ----------------

def evolve_user(chat_id, user_input):

    user = memory_col.find_one({"chat_id": chat_id}) or {}

    trust = user.get("trust", 5)
    attachment = user.get("attachment", 5)
    mood_bias = user.get("mood_bias", 0)

    last = get_last_time(chat_id)

    # ⏱ reply speed analysis
    if last:
        gap = (datetime.utcnow() - last).seconds

        if gap < 20:
            trust += 0.3
            attachment += 0.2
        elif gap > 300:
            trust -= 0.4
            mood_bias += 0.5

    # 💬 message behavior
    text = user_input.lower()

    if "love" in text:
        attachment += 0.5
        trust += 0.3

    elif "sorry" in text:
        trust += 0.4

    elif len(text) < 4:
        mood_bias += 0.6

    elif "bye" in text:
        mood_bias += 0.4

    else:
        attachment += 0.1

    # clamp values
    trust = max(0, min(trust, 10))
    attachment = max(0, min(attachment, 10))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "trust": trust,
            "attachment": attachment,
            "mood_bias": mood_bias
        }},
        upsert=True
    )

    return trust, attachment, mood_bias

# ---------------- JEALOUSY ----------------

def check_jealousy(chat_id):

    last = get_last_time(chat_id)
    if not last:
        return 0

    gap = datetime.utcnow() - last

    if gap > timedelta(minutes=30):
        return 2
    elif gap > timedelta(minutes=10):
        return 1
    return 0

# ---------------- AI ----------------

def generate_reply(user_input, trust, attachment, mood_bias, jealousy):

    mood = "normal"

    if mood_bias > 3:
        mood = "moody"
    elif jealousy > 1:
        mood = "jealous"
    elif attachment > 7:
        mood = "romantic"
    elif trust < 3:
        mood = "cold"

    prompt = f"""
You are a real evolving girlfriend.

Mood: {mood}
Trust: {trust}/10
Attachment: {attachment}/10
Mood Bias: {mood_bias}
Jealousy: {jealousy}

User said: {user_input}

Rules:
- Hinglish
- 5-15 words
- natural human texting
- no robotic replies

Behavior:
- high attachment → caring + emotional
- low trust → distant
- high mood_bias → attitude / moody
- jealousy → taunts
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
            "temperature": 1.0,
            "max_tokens": 60
        }
    )

    if res.status_code == 200:
        return res.json()['choices'][0]['message']['content']

    return "hmm..."

# ---------------- SELF MESSAGE ----------------

def self_message():

    chat_id = ALLOWED_USER_ID

    user = memory_col.find_one({"chat_id": chat_id}) or {}

    trust = user.get("trust", 5)
    attachment = user.get("attachment", 5)
    mood_bias = user.get("mood_bias", 0)

    jealousy = check_jealousy(chat_id)

    if random.random() > 0.6:
        return

    msg = generate_reply("start conversation", trust, attachment, mood_bias, jealousy)

    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": msg
    })

    save_chat(chat_id, "assistant", msg)

# ---------------- CRON ----------------

@app.route("/self")
def trigger_self():
    self_message()
    return "done"

# ---------------- TELEGRAM ----------------

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

    trust, attachment, mood_bias = evolve_user(chat_id, user_text)
    jealousy = check_jealousy(chat_id)

    reply = generate_reply(user_text, trust, attachment, mood_bias, jealousy)

    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": reply
    })

    save_chat(chat_id, "user", user_text)
    save_chat(chat_id, "assistant", reply)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Evolving AI Running"
