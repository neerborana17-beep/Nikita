import os, requests, random, time
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime
import pytz

app = Flask(__name__)

# ------------------ ENV ------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# 🔐 ONLY YOU CAN USE
ALLOWED_USER_ID = 6243559768   # ⚠️ yaha apna Telegram ID daalo

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ------------------ DB ------------------

memory_col = None
history_col = None

try:
    if MONGO_URI:
        client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = client['zayra_ai']
        memory_col = db['user_memory']
        history_col = db['chat_history']
        print("✅ Mongo Connected")
except Exception as e:
    print("Mongo Error:", e)

# ------------------ TIME ------------------

def get_time():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    return now.strftime("%I:%M %p"), now.strftime("%A")

# ------------------ MEMORY ------------------

def extract_name(text):
    t = text.lower()
    if "i am" in t:
        return text.split("i am")[-1].strip()
    if "i'm" in t:
        return text.split("i'm")[-1].strip()
    if "mera naam" in t:
        return text.split()[-1]
    return None

def get_memory(chat_id):
    if memory_col is not None:
        return memory_col.find_one({"chat_id": chat_id}) or {}
    return {}

def update_memory(chat_id, user_input):
    if memory_col is None:
        return

    data = {"chat_id": chat_id}

    name = extract_name(user_input)
    if name:
        data["name"] = name.capitalize()

    user = memory_col.find_one({"chat_id": chat_id}) or {}
    level = user.get("level", 1)
    level = min(level + 0.1, 10)

    data["level"] = level

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": data},
        upsert=True
    )

# ------------------ HISTORY ------------------

def save_chat(chat_id, role, content):
    if history_col is not None:
        history_col.insert_one({
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "time": datetime.utcnow()
        })

def get_history(chat_id):
    if history_col is not None:
        msgs = list(history_col.find({"chat_id": chat_id})
                    .sort("time", -1).limit(10))
        msgs.reverse()
        return msgs
    return []

# ------------------ AI ------------------

def detect_mood(text):
    t = text.lower()
    if "sad" in t:
        return "emotional"
    if "miss" in t or "love" in t:
        return "romantic"
    if "gussa" in t:
        return "angry"
    return "normal"

def get_ai_response(user_input, memory, history):

    name = memory.get("name", "")
    level = memory.get("level", 1)
    mood = detect_mood(user_input)

    current_time, day = get_time()

    past = ""
    for msg in history:
        past += f"{msg['role']}: {msg['content']}\n"

    system_prompt = f"""
You are Zayra, a real girlfriend.

Time: {current_time}, Day: {day}
User: {name}
Relationship level: {level}/10
Mood: {mood}

Past chats:
{past}

PERSONALITY:
- caring ❤️
- jealous 😒
- teasing 😏
- moody 😤

BEHAVIOR:
- remembers past
- sometimes mentions old talks
- reacts emotionally

STYLE:
- Hinglish
- 5-15 words
- max 1 emoji
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
                "temperature": 0.95,
                "max_tokens": 100
            },
            timeout=20
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']

        return "net slow h"

    except Exception as e:
        print("AI Error:", e)
        return "server busy h"

# ------------------ TELEGRAM ------------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        message = data.get("message")
        if not message:
            return {"ok": True}

        chat_id = message.get("chat", {}).get("id")

        # 🔐 BLOCK OTHER USERS
        if chat_id != ALLOWED_USER_ID:
            return {"ok": True}

        user_text = message.get("text")
        if not user_text:
            return {"ok": True}

        memory = get_memory(chat_id)
        history = get_history(chat_id)

        # ⏳ Seen delay
        time.sleep(random.uniform(0.5, 1.2))

        # ✍️ typing
        requests.post(f"{TELEGRAM_API}/sendChatAction", json={
            "chat_id": chat_id,
            "action": "typing"
        })

        time.sleep(random.uniform(1, 2))

        reply = get_ai_response(user_text, memory, history)

        time.sleep(min(len(reply)*0.05, 3))

        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": reply
        })

        save_chat(chat_id, "user", user_text)
        save_chat(chat_id, "assistant", reply)

        update_memory(chat_id, user_text)

        print("✅ Reply:", reply)

    except Exception as e:
        print("❌ ERROR:", e)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Private AI Running 🔒"

if __name__ == "__main__":
    app.run(port=10000)
