import os, requests, random, time
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# ---------------- ENV ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------------- DB ----------------

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zayra_ai']

history_col = db['chat_history']
memory_col = db['memory']
dataset_col = db['dataset']

# ---------------- TIME ----------------

def get_time():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

# ---------------- USER ----------------

def get_user_role(chat_id):
    return "owner" if chat_id == ALLOWED_USER_ID else "other"

# ---------------- MEMORY ----------------

def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, user_text):

    mem = get_memory(chat_id)

    attach = mem.get("attachment", 20)
    reward = mem.get("reward", 0)

    t = user_text.lower()

    if any(x in t for x in ["love","miss","good"]):
        attach += 2
        reward += 2
    elif any(x in t for x in ["bad","hate","ignore"]):
        attach -= 2
        reward -= 2
    elif len(t) < 4:
        attach -= 0.2

    attach = max(0, min(100, attach))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": attach,
            "reward": reward
        }},
        upsert=True
    )

# ---------------- DATASET ----------------

def learn_dataset(user_text, reply):

    if len(user_text) > 3 and len(reply) > 3:
        dataset_col.insert_one({
            "user": user_text.lower(),
            "reply": reply
        })

def get_dataset_reply(user_text):

    data = dataset_col.find_one({"user": user_text.lower()})
    return data["reply"] if data else None

# ---------------- REAL LIFE ----------------

def real_life():

    h = get_time().hour

    if h < 11:
        return random.choice(["abhi uthi hu","chai pi rhi hu"])
    elif h < 17:
        return random.choice(["college me hu","class chal rhi"])
    elif h < 21:
        return random.choice(["ghar aa gyi hu","thodi tired hu"])
    else:
        return random.choice(["bed pe hu","sona hai"])

# ---------------- BRAIN ----------------

def brain(user_text, mem):

    attach = mem.get("attachment", 20)
    t = user_text.lower()

    if t in ["hmm","ok","hn","acha"]:
        return random.choice(["hmm","acha","hn"])

    if attach > 70:
        return random.choice([
            "tumse baat acchi lagti h",
            "tum thode special ho"
        ])

    if attach > 40:
        return random.choice([
            "tum bhi na 😏",
            "acha ji"
        ])

    return None

# ---------------- PERSONALITY ----------------

PERSONALITY = """
You are Zayra.

- 19 year old girl
- Jaipur, Rajasthan
- LLB student

STYLE:
- short replies
- hinglish
- teasing + caring
- natural texting

RULES:
- never robotic
- no long paragraphs
- human-like tone
"""

# ---------------- AI ----------------

def ai_reply(user_text, history):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    prompt = f"""
{PERSONALITY}

Current life:
{real_life()}

CHAT:
{context}

User: {user_text}

RULES:
- continue topic
- short replies
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

# ---------------- IMAGE ----------------

def handle_image(chat_id):

    mem = get_memory(chat_id)
    attach = mem.get("attachment", 20)

    if attach > 60:
        return random.choice([
            "ye kaun h 😒",
            "acha pic h",
            "hmm…"
        ])

    return "nice pic"

# ---------------- AUTO MESSAGE ----------------

def auto_message(chat_id):

    mem = get_memory(chat_id)
    last = mem.get("last_auto")
    now = datetime.utcnow()

    if last:
        if (now - last).total_seconds() < random.randint(900,1800):
            return

    if random.random() > 0.6:
        return

    msg = random.choice([
        "kya kar rahe ho",
        "yaad aayi tumhari",
        real_life()
    ])

    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_auto": now}},
        upsert=True
    )

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

    # ---------------- IMAGE ----------------
    if "photo" in message:
        reply = handle_image(chat_id)
        send(chat_id, reply)
        return {"ok": True}

    user_text = message.get("text")
    if not user_text:
        return {"ok": True}

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    update_memory(chat_id, user_text)
    mem = get_memory(chat_id)

    # 1️⃣ dataset
    reply = get_dataset_reply(user_text)

    # 2️⃣ brain
    if not reply:
        decision = brain(user_text, mem)
        if decision:
            reply = decision

    # 3️⃣ AI
    if not reply:
        reply = ai_reply(user_text, history)

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

    learn_dataset(user_text, reply)

    if random.random() < 0.3:
        auto_message(chat_id)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra AI Running"
