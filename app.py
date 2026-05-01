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

def save(chat_id, role, text):
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

# ---------------- MEMORY ----------------

def update_memory(chat_id, user_text):
    mem = memory_col.find_one({"chat_id": chat_id}) or {}

    attach = mem.get("attachment", 10)

    if len(user_text) < 4:
        attach -= 1
    elif "love" in user_text.lower():
        attach += 2
    else:
        attach += 0.3

    attach = max(0, min(100, attach))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"attachment": attach}},
        upsert=True
    )

    return attach

# ---------------- TIME ----------------

def get_time_mood():
    h = datetime.now().hour
    if h < 12:
        return "morning"
    elif h < 18:
        return "day"
    else:
        return "night"

# ---------------- BRAIN ----------------

def decide_mode(user_text, attach):
    t = user_text.lower()

    if t in ["hmm","ok","hn","acha"]:
        return "short"

    if "love" in t or "miss" in t:
        return "emotional"

    if attach > 80:
        return random.choice(["romantic","tease","soft"])

    return random.choice(["short","normal","tease","ignore"])

# ---------------- AI ----------------

def ai_reply(user_text, history, attach):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    time_mood = get_time_mood()
    mode = decide_mode(user_text, attach)

    prompt = f"""
You are Zayra (Jaipur, LLB girl).

Time: {time_mood}
Attachment: {attach}

CHAT:
{context}

User: {user_text}

RULES:

- Hinglish
- short replies preferred
- real girl texting style
- imperfect sentences allowed
- sometimes incomplete reply
- no robotic tone

BEHAVIOR:

- morning → sleepy
- night → emotional
- high attachment → soft / possessive

- sometimes:
  - ignore
  - tease
  - double message

EXAMPLES:
"hmm"
"acha suno"
"tum na…"
"chodo"
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

# ---------------- SEND ----------------

def send(chat_id, text):
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

    user_text = message.get("text")

    if not user_text:
        return {"ok": True}

    # 🧠 update memory
    attach = update_memory(chat_id, user_text)

    # 🧠 history
    history = get_history(chat_id)

    # 🤖 thinking delay
    time.sleep(random.uniform(0.8, 2))

    # typing
    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    reply = ai_reply(user_text, history, attach)

    # 🎭 human behavior
    if random.random() < 0.2:
        reply = reply.lower()

    if random.random() < 0.15:
        reply = reply[:len(reply)//2]

    # double msg
    if random.random() < 0.2:
        send(chat_id, reply[:len(reply)//2])
        time.sleep(1)
        send(chat_id, reply[len(reply)//2:])
    else:
        send(chat_id, reply)

    save(chat_id, "user", user_text)
    save(chat_id, "assistant", reply)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Ultra Real AI Running"
