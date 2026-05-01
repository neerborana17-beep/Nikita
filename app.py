import os, requests, random, time
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

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zayra_ai']

history_col = db['chat_history']
memory_col = db['memory']

# ---------------- TIME ----------------

def get_time():
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.now(ist)

# ---------------- MEMORY ----------------

def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, user_text):

    mem = get_memory(chat_id)

    attach = mem.get("attachment", 20)
    mood = mem.get("mood", "normal")
    trust = mem.get("trust", 10)
    hurt = mem.get("hurt", 0)

    text = user_text.lower()

    # ❤️ emotional bonding
    if "miss" in text or "love" in text:
        attach += 2
        trust += 1

    elif "sorry" in text:
        hurt = max(0, hurt - 2)
        trust += 1

    elif len(text) < 4:
        attach -= 0.3

    # 💔 hurt system
    if "ignore" in text:
        hurt += 1

    attach = max(0, min(100, attach))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": attach,
            "mood": mood,
            "trust": trust,
            "hurt": hurt
        }},
        upsert=True
    )

    return attach, mood, trust, hurt

# ---------------- MEMORY RECALL ----------------

def recall(history):

    if len(history) < 3:
        return ""

    last_user = [m["content"] for m in history if m["role"] == "user"]

    if len(last_user) >= 2:
        return f"User earlier said: {last_user[-2]}"

    return ""

# ---------------- IMAGE DETECTION (HACK) ----------------

def detect_image_type(message):

    caption = message.get("caption", "").lower()

    if any(x in caption for x in ["girl","she","her"]):
        return "girl"

    if any(x in caption for x in ["me","self","my"]):
        return "self"

    return "unknown"

def image_reply(chat_id, message):

    mem = get_memory(chat_id)
    attach = mem.get("attachment", 20)

    img_type = detect_image_type(message)

    if img_type == "girl":
        if attach > 60:
            return random.choice([
                "ye kaun h 😒",
                "tumhari friend h kya",
                "hmm… acha"
            ])
        else:
            return "nice pic"

    if img_type == "self":
        return random.choice([
            "acha lag rahe ho",
            "selfie mood 😏",
            "hero lag rahe"
        ])

    return random.choice([
        "kaha ki h ye",
        "nice pic",
        "kab ki h"
    ])

# ---------------- BRAIN ----------------

def brain(user_text, attach, trust, hurt):

    t = user_text.lower()

    # short
    if t in ["hmm","ok","hn","acha"]:
        return random.choice(["hmm", "acha", "hn"])

    # 💔 hurt reaction
    if hurt > 2:
        return random.choice([
            "tum change lag rahe ho",
            "pehle aise nahi the",
            "theek ho?"
        ])

    # ❤️ deep bonding
    if attach > 75:
        return random.choice([
            "tumse baat karke acha lagta h",
            "tum important ho thode",
            "miss karti hu kabhi kabhi"
        ])

    # 😏 mid
    if attach > 40:
        return random.choice([
            "tum bhi na 😏",
            "acha ji",
            "zyada mat bolo"
        ])

    return None

# ---------------- AI ----------------

def ai_reply(user_text, history, attach, mood):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    prompt = f"""
You are Zayra.

- Jaipur girl
- LLB student
- soft + teasing + caring

Attachment: {attach}

CHAT:
{context}

User: {user_text}

RULES:

- short replies
- natural hinglish
- no repetition
- continue topic
- real girl tone

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
            "temperature": 0.9,
            "max_tokens": 60
        }
    )

    if res.status_code == 200:
        return res.json()['choices'][0]['message']['content']

    return "hmm"

# ---------------- SEND ----------------

def send(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

# ---------------- AUTO MESSAGE ----------------

def auto_message():

    chat_id = ALLOWED_USER_ID

    last = history_col.find_one({"chat_id": chat_id}, sort=[("time",-1)])

    if last:
        gap = datetime.utcnow() - last["time"]
        if gap < timedelta(minutes=20):
            return

    msgs = [
        "kya kar rahe ho",
        "aaj yaad nahi kiya",
        "busy ho kya",
        "acha suno"
    ]

    msg = random.choice(msgs)

    send(chat_id, msg)

    history_col.insert_one({
        "chat_id": chat_id,
        "role": "assistant",
        "content": msg,
        "time": datetime.utcnow()
    })

# ---------------- MAIN ----------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    data = request.get_json()
    message = data.get("message")

    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")

    if chat_id != ALLOWED_USER_ID:
        return {"ok": True}

    # IMAGE
    if "photo" in message:
        reply = image_reply(chat_id, message)
        send(chat_id, reply)
        return {"ok": True}

    user_text = message.get("text")

    if not user_text:
        return {"ok": True}

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    attach, mood, trust, hurt = update_memory(chat_id, user_text)

    # 🧠 brain
    decision = brain(user_text, attach, trust, hurt)

    if decision:
        reply = decision
    else:
        reply = ai_reply(user_text, history, attach, mood)

    time.sleep(random.uniform(1,2))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    send(chat_id, reply)

    history_col.insert_one({
        "chat_id": chat_id,
        "role": "user",
        "content": user_text,
        "time": datetime.utcnow()
    })

    history_col.insert_one({
        "chat_id": chat_id,
        "role": "assistant",
        "content": reply,
        "time": datetime.utcnow()
    })

    return {"ok": True}

@app.route("/self")
def trigger_self():
    auto_message()
    return "ok"

@app.route("/")
def home():
    return "Zayra Ultimate Brain AI Running"
