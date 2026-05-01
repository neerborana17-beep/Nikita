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
                .sort("time", -1).limit(8))
    msgs.reverse()
    return msgs

# ---------------- RELATIONSHIP ENGINE ----------------

def update_relationship(chat_id, user_text):

    mem = memory_col.find_one({"chat_id": chat_id}) or {}

    love = mem.get("love", 5)
    anger = mem.get("anger", 0)
    jealousy = mem.get("jealousy", 0)

    text = user_text.lower()

    # ❤️ patch-up
    if "sorry" in text or "love" in text:
        anger = max(0, anger - 2)
        love += 1

    # 💔 fight triggers
    elif len(text) < 4:
        anger += 1
        jealousy += 0.5

    elif "bye" in text:
        anger += 1

    else:
        love += 0.2
        anger = max(0, anger - 0.2)

    love = min(love, 10)
    jealousy = min(jealousy, 10)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "love": love,
            "anger": anger,
            "jealousy": jealousy
        }},
        upsert=True
    )

    return love, anger, jealousy

# ---------------- JEALOUSY CHECK ----------------

def check_jealousy(chat_id):

    last = history_col.find_one({"chat_id": chat_id}, sort=[("time",-1)])

    if not last:
        return 0

    gap = datetime.utcnow() - last["time"]

    if gap > timedelta(minutes=30):
        return 2
    elif gap > timedelta(minutes=15):
        return 1

    return 0

# ---------------- AI ----------------

def get_ai_reply(user_input, history, memory, love, anger, jealousy):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    mood = "normal"

    if anger > 3:
        mood = "angry"
    elif jealousy > 2:
        mood = "jealous"
    elif love > 7:
        mood = "romantic"

    prompt = f"""
You are Zayra (Jaipur, LLB student).

Mood: {mood}
Love: {love}
Anger: {anger}
Jealousy: {jealousy}

CHAT:
{context}

USER:
{user_input}

RULES:

- Hinglish
- short (5-12 words)
- continue same topic
- no robotic reply

BEHAVIOR:

- angry → attitude, short
- jealous → taunt
- romantic → soft
- normal → casual

Examples:
- "ab yaad aayi meri?"
- "kisi aur se busy the kya"
- "hmm theek hai"
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

# ---------------- SELF MESSAGE ----------------

def self_message():

    chat_id = ALLOWED_USER_ID

    jealousy = check_jealousy(chat_id)

    if random.random() > 0.5:
        return

    if jealousy > 1:
        msg = "ab kisi aur se baat ho rhi thi kya"
    else:
        msg = random.choice([
            "kya kar rahe ho",
            "yaad hi nahi kiya",
            "busy ho kya"
        ])

    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": msg
    })

    save_chat(chat_id, "assistant", msg)

# ---------------- REPLY ----------------

def send_reply(chat_id, user_text):

    time.sleep(random.uniform(0.5,1.5))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    history = get_history(chat_id)

    love, anger, jealousy = update_relationship(chat_id, user_text)
    jealousy += check_jealousy(chat_id)

    memory = memory_col.find_one({"chat_id": chat_id}) or {}

    reply = get_ai_reply(user_text, history, memory, love, anger, jealousy)

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
    return "Zayra Advanced AI Running"
