import os, requests, random, time
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime
import pytz

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ------------------ DB ------------------

memory_col = None
history_col = None

if MONGO_URI:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['zayra_ai']
    memory_col = db['user_memory']
    history_col = db['chat_history']

# ------------------ TIME ------------------

def get_time_context():
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
    if memory_col:
        user = memory_col.find_one({"chat_id": chat_id})
        return user if user else {}
    return {}

def update_memory(chat_id, user_input):
    if not memory_col:
        return

    data = {"chat_id": chat_id}

    name = extract_name(user_input)
    if name:
        data["name"] = name.capitalize()

    # relationship level increase
    user = memory_col.find_one({"chat_id": chat_id}) or {}
    level = user.get("level", 1)
    level = min(level + 0.1, 10)
    data["level"] = level

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": data},
        upsert=True
    )

# ------------------ CHAT HISTORY ------------------

def save_chat(chat_id, role, content):
    if history_col:
        history_col.insert_one({
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "time": datetime.utcnow()
        })

def get_history(chat_id):
    if history_col:
        msgs = list(history_col.find({"chat_id": chat_id})
                    .sort("time", -1).limit(10))
        msgs.reverse()
        return msgs
    return []

# ------------------ MOOD ------------------

def detect_mood(text):
    t = text.lower()
    if "sad" in t:
        return "emotional"
    if "love" in t or "miss" in t:
        return "romantic"
    if "gussa" in t:
        return "angry"
    return "normal"

# ------------------ AI ------------------

def get_ai_response(user_input, memory, history):

    name = memory.get("name", "")
    level = memory.get("level", 1)
    mood = detect_mood(user_input)

    current_time, day = get_time_context()

    # convert history
    past = ""
    for msg in history:
        past += f"{msg['role']}: {msg['content']}\n"

    system_prompt = f"""
You are Zayra, a real girlfriend.

Time: {current_time}, Day: {day}

User name: {name}
Relationship level: {level}/10
Mood: {mood}

Past chats:
{past}

PERSONALITY:
- caring ❤️
- jealous 😒
- teasing 😏
- moody 😤
- emotional bonding

BEHAVIOR:
- high level → more love
- low level → more attitude
- याद रखती है past बातें
- कभी कभी पुरानी बात mention करो

STYLE:
- short Hinglish replies
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
            }
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']

        return "net slow h"

    except:
        return "server busy h"

# ------------------ TELEGRAM ------------------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    message = data.get("message")
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text")

    if not user_text:
        return {"ok": True}

    memory = get_memory(chat_id)
    history = get_history(chat_id)

    time.sleep(random.uniform(0.5, 1.2))

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

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra AI Running"

if __name__ == "__main__":
    app.run(port=10000)
