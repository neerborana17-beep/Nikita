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

# ---------------- HUMAN BRAIN ----------------

def decide_behavior(user_text):

    t = user_text.lower()

    # short reply cases
    if t in ["hmm","ok","hn","acha"]:
        return "short"

    # emotional
    if "love" in t or "miss" in t:
        return "emotional"

    # question
    if "?" in t:
        return "answer"

    # default random
    return random.choice(["short","normal","tease"])

# ---------------- AI ----------------

def get_ai_reply(user_input, history, mode):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    length_rule = ""

    if mode == "short":
        length_rule = "reply in 1-3 words only"
    elif mode == "normal":
        length_rule = "reply in 5-10 words"
    elif mode == "emotional":
        length_rule = "slightly emotional 8-15 words"
    elif mode == "tease":
        length_rule = "light teasing short reply"

    prompt = f"""
You are Zayra (Jaipur, LLB girl).

CHAT:
{context}

User: {user_input}

RULES:
- Hinglish
- {length_rule}
- natural human reply
- no robotic tone
- continue same topic
- sometimes incomplete sentence

GENDER:
user male → rha hu
you female → rhi hu
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

# ---------------- REPLY ----------------

def send_reply(chat_id, user_text):

    # 👀 thinking delay
    time.sleep(random.uniform(0.8, 2))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    history = get_history(chat_id)

    # 🧠 brain decision
    mode = decide_behavior(user_text)

    reply = get_ai_reply(user_text, history, mode)

    # 🧠 human imperfection
    if random.random() < 0.2:
        reply = reply.lower()

    if random.random() < 0.15:
        reply = reply[:max(3, len(reply)//2)]  # incomplete sentence

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

@app.route("/")
def home():
    return "Zayra Brain AI Running"
