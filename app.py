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
memory_col = db['memory']

# ---------------- SAVE ----------------

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

# ---------------- RELATIONSHIP ENGINE ----------------

def update_relationship(chat_id, user_text):

    mem = memory_col.find_one({"chat_id": chat_id}) or {}

    attach = mem.get("attachment", 10)
    mood = mem.get("mood", "normal")

    text = user_text.lower()

    # ❤️ attachment growth
    if any(x in text for x in ["love","miss","cute","acha lagta"]):
        attach += 2
    elif len(text) < 4:
        attach -= 1
    else:
        attach += 0.3

    # 💔 negative behavior
    if any(x in text for x in ["bye","jao","mat baat karo"]):
        attach -= 2

    attach = max(0, min(100, attach))

    # 🎭 mood shift
    if attach < 30:
        mood = "normal"
    elif attach < 60:
        mood = "friendly"
    elif attach < 80:
        mood = "caring"
    elif attach < 95:
        mood = "attached"
    else:
        mood = "gf"

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": attach,
            "mood": mood
        }},
        upsert=True
    )

    return attach, mood

# ---------------- AI ----------------

def get_ai_reply(user_input, history, attach, mood):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    # 💞 behavior style
    style = ""

    if mood == "normal":
        style = "casual friend"
    elif mood == "friendly":
        style = "slightly interested"
    elif mood == "caring":
        style = "soft caring tone"
    elif mood == "attached":
        style = "emotionally attached, थोड़ा possessive"
    elif mood == "gf":
        style = "girlfriend vibe, emotional + teasing + possessive"

    prompt = f"""
You are Zayra (Jaipur, LLB student).

Attachment level: {attach}
Mood: {mood}

Behavior: {style}

CHAT:
{context}

USER:
{user_input}

RULES:

- Hinglish
- short replies (3-10 words)
- natural texting (not perfect grammar)
- continue same topic
- no robotic replies

SPECIAL:

- if mood=gf → show slight jealousy
- if mood=attached → emotional hints
- if mood=low → neutral tone

EXAMPLES:
- "tum bhi na"
- "acha 😏"
- "miss kiya mujhe?"
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
            "temperature": 0.95,
            "max_tokens": 60
        }
    )

    if res.status_code == 200:
        return res.json()['choices'][0]['message']['content']

    return "hmm"

# ---------------- SELF MESSAGE ----------------

def self_message():

    chat_id = ALLOWED_USER_ID

    mem = memory_col.find_one({"chat_id": chat_id}) or {}
    attach = mem.get("attachment", 10)

    last = history_col.find_one({"chat_id": chat_id}, sort=[("time",-1)])

    if last:
        gap = datetime.utcnow() - last["time"]
        if gap < timedelta(minutes=15):
            return

    if random.random() > 0.5:
        return

    # 💞 behavior based self msg
    if attach > 80:
        msg = random.choice([
            "tum yaad aa rahe the",
            "kya kar rahe ho abhi",
            "miss kar rhi hu thoda"
        ])
    else:
        msg = random.choice([
            "kya kar rahe ho",
            "busy ho kya",
            "acha suno"
        ])

    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": msg
    })

    save_chat(chat_id, "assistant", msg)

# ---------------- REPLY ----------------

def send_reply(chat_id, user_text):

    time.sleep(random.uniform(0.8,1.8))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    history = get_history(chat_id)

    attach, mood = update_relationship(chat_id, user_text)

    reply = get_ai_reply(user_text, history, attach, mood)

    # short reply logic
    if random.random() < 0.25:
        reply = random.choice(["hmm", "acha", "hn"])

    time.sleep(min(max(len(reply)*0.05,1),3))

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

@app.route("/self")
def trigger_self():
    self_message()
    return "ok"

@app.route("/")
def home():
    return "Zayra Ultimate GF AI Running"
