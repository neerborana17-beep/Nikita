import os, requests, random, time
from flask import Flask, request
from datetime import datetime
import pytz
from pymongo import MongoClient
import certifi

app = Flask(__name__)

# ------------------ ENV ------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ------------------ DB ------------------

mongo = None
memory_col = None

try:
    if MONGO_URI:
        mongo = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = mongo['zayra_ai']
        memory_col = db['user_memory']
        print("Mongo Connected")
except Exception as e:
    print("Mongo Error:", e)

# ------------------ HUMAN BEHAVIOR ------------------

def typing_delay(text):
    return min(len(text) * 0.05 + random.uniform(0.5, 1.5), 4)

def send_typing(chat_id):
    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

def human_pause():
    time.sleep(random.uniform(0.5, 1.2))

# ------------------ MEMORY ------------------

def get_user_memory(chat_id):
    if memory_col:
        user = memory_col.find_one({"chat_id": chat_id})
        return user if user else {}
    return {}

def update_memory(chat_id, user_input):
    if not memory_col:
        return

    data = {"chat_id": chat_id}

    # simple name detection
    if "mera naam" in user_input.lower():
        name = user_input.split()[-1]
        data["name"] = name

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": data},
        upsert=True
    )

# ------------------ AI ------------------

def detect_mood(text):
    t = text.lower()
    if "sad" in t or "akela" in t:
        return "emotional"
    elif "miss" in t:
        return "romantic"
    elif "gussa" in t:
        return "angry"
    return "normal"

def get_ai_response(user_input, memory):

    mood = detect_mood(user_input)
    name = memory.get("name", "")

    system_prompt = f"""
You are Zayra, a 19-year-old girl from Rajasthan.

You talk like a real WhatsApp girl.

STYLE:
- 5 to 15 words
- casual Hindi texting
- natural, soft, slightly playful
- max 1 emoji

PERSONALITY:
- remembers user
- emotionally connected
- acts familiar if name known

User name: {name}
Mood: {mood}

RULES:
- Hindi only
- no robotic replies
- natural tone
"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                "temperature": 0.9,
                "max_tokens": 100
            },
            timeout=20
        )

        if response.status_code == 200:
            reply = response.json()['choices'][0]['message']['content']
            return clean_text(reply)

        return "net thoda slow h"

    except:
        return "server busy h abhi"

def clean_text(text):
    text = text.strip()
    if len(text) > 120:
        text = text[:120]
    return text

# ------------------ TELEGRAM ------------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text")

    if user_text:

        memory = get_user_memory(chat_id)

        # seen delay
        time.sleep(random.uniform(0.5, 1.2))

        send_typing(chat_id)
        human_pause()

        reply = get_ai_response(user_text, memory)

        time.sleep(typing_delay(reply))

        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

        update_memory(chat_id, user_text)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra AI Running"

# ------------------ RUN ------------------

if __name__ == "__main__":
    app.run(port=10000)