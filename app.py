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

# ---------------- MEMORY ----------------

def update_image_memory(chat_id):
    mem = memory_col.find_one({"chat_id": chat_id}) or {}
    count = mem.get("image_count", 0) + 1

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"image_count": count}},
        upsert=True
    )

def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

# ---------------- IMAGE REACTION ----------------

def generate_image_reply(chat_id):

    mem = get_memory(chat_id)
    count = mem.get("image_count", 1)

    mode = random.choice(["compliment","tease","observe","memory"])

    # 🔥 compliment
    compliments = [
        "acha lag rahe ho 😏",
        "kaafi smart lag rahe ho",
        "nice pic h",
        "ye look acha h tumpe"
    ]

    # 😏 tease
    tease = [
        "itna ready kis ke liye hue ho 😏",
        "selfie mode me ho aaj",
        "koi special h kya 😂",
        "pose to full hero wala h"
    ]

    # 👀 observe
    observe = [
        "ye pic kab ki h?",
        "nayi lag rhi h",
        "acha background h",
        "kaha click ki ye"
    ]

    # 🧠 memory based
    memory_lines = [
        "tum pics bhejna pasand karte ho na",
        "pehle bhi aisi pic bheji thi",
        "aajkal kaafi pics aa rhi h 😏"
    ]

    if mode == "compliment":
        reply = random.choice(compliments)
    elif mode == "tease":
        reply = random.choice(tease)
    elif mode == "observe":
        reply = random.choice(observe)
    else:
        if count > 2:
            reply = random.choice(memory_lines)
        else:
            reply = random.choice(observe)

    # 🔥 short natural filter
    if random.random() < 0.3:
        reply = reply.replace("rahe ho", "rhe ho")

    return reply

# ---------------- TEXT AI ----------------

def text_reply(user_text):

    prompt = f"""
You are Zayra (Jaipur girl).

User: {user_text}

Reply:
- Hinglish
- very short
- natural human tone
- emotional + teasing
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

def send_msg(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
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

    # 📸 IMAGE DETECT
    if "photo" in message:

        update_image_memory(chat_id)

        time.sleep(random.uniform(1,2))

        reply = generate_image_reply(chat_id)

        send_msg(chat_id, reply)

        save_chat(chat_id, "user", "[image]")
        save_chat(chat_id, "assistant", reply)

        return {"ok": True}

    # 💬 TEXT
    user_text = message.get("text")

    if not user_text:
        return {"ok": True}

    time.sleep(random.uniform(0.5,1.5))

    reply = text_reply(user_text)

    send_msg(chat_id, reply)

    save_chat(chat_id, "user", user_text)
    save_chat(chat_id, "assistant", reply)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Free Vision AI Running"
