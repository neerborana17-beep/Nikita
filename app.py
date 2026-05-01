import os, requests, random, time
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime

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

# ---------------- SAVE CHAT ----------------

def save_chat(chat_id, role, text):
    history_col.insert_one({
        "chat_id": chat_id,
        "role": role,
        "content": text,
        "time": datetime.utcnow()
    })

# ---------------- RELATIONSHIP MEMORY ----------------

def update_relationship(chat_id, user_input):

    user = memory_col.find_one({"chat_id": chat_id}) or {}

    trust = user.get("trust", 5)
    attachment = user.get("attachment", 5)

    text = user_input.lower()

    if "love" in text:
        trust += 0.4
        attachment += 0.6

    elif "sorry" in text:
        trust += 0.5

    elif len(text) < 4:
        trust -= 0.3

    elif "bye" in text:
        attachment -= 0.4

    else:
        attachment += 0.1

    trust = max(0, min(trust, 10))
    attachment = max(0, min(attachment, 10))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"trust": trust, "attachment": attachment}},
        upsert=True
    )

    return trust, attachment

# ---------------- TYPO SYSTEM ----------------

def add_typo(text):
    words = text.split()

    if len(words) == 0:
        return text

    if random.random() < 0.4:
        i = random.randint(0, len(words)-1)
        w = words[i]

        if len(w) > 3:
            w = w.replace("a", "").replace("e", "")
            words[i] = w

    return " ".join(words)

# ---------------- LOWERCASE ----------------

def humanize_text(text):
    text = text.lower()
    text = add_typo(text)
    return text

# ---------------- AI ----------------

def get_ai_reply(user_input, trust, attachment):

    mood = "normal"

    if attachment > 7:
        mood = "romantic"
    elif trust < 3:
        mood = "cold"

    prompt = f"""
You are a real girlfriend.

Mood: {mood}
Trust: {trust}/10
Attachment: {attachment}/10

User: {user_input}

Rules:
- Hinglish
- short natural reply
- human tone
- not perfect
- sometimes emotional
- sometimes dry
- not always asking question
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

    return "hmm thik hai"

# ---------------- HUMAN BEHAVIOR ----------------

def send_typing(chat_id):
    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

def send_message(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

# ---------------- RESPONSE ENGINE ----------------

def send_human_reply(chat_id, user_text):

    # 👀 seen delay
    time.sleep(random.uniform(0.5, 1.5))

    send_typing(chat_id)

    memory = memory_col.find_one({"chat_id": chat_id}) or {}

    trust, attachment = update_relationship(chat_id, user_text)

    reply = get_ai_reply(user_text, trust, attachment)

    reply = humanize_text(reply)

    # ⏳ typing delay
    time.sleep(min(max(len(reply)*0.05, 1), 3))

    mode = random.random()

    # NORMAL
    if mode < 0.5:
        send_message(chat_id, reply)

    # DOUBLE MESSAGE
    elif mode < 0.8:
        mid = len(reply)//2
        send_message(chat_id, reply[:mid])

        time.sleep(random.uniform(0.8, 1.5))
        send_typing(chat_id)
        time.sleep(random.uniform(0.5, 1.2))

        send_message(chat_id, reply[mid:])

    # EDIT SIMULATION
    else:
        short = reply[:len(reply)//2]
        send_message(chat_id, short)

        time.sleep(random.uniform(0.8, 1.5))
        send_typing(chat_id)
        time.sleep(random.uniform(1, 2))

        send_message(chat_id, reply)

    save_chat(chat_id, "user", user_text)
    save_chat(chat_id, "assistant", reply)

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

    if not user_text:
        return {"ok": True}

    send_human_reply(chat_id, user_text)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Ultra Human AI Running"
