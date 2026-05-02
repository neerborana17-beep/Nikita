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
dataset_col = db['dataset']

# ---------------- TIME ----------------

def get_time():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

# ---------------- MEMORY ----------------

def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

# ---------------- RL SYSTEM ----------------

def update_rl(chat_id, user_text):
    mem = get_memory(chat_id)
    reward = mem.get("reward", 0)

    t = user_text.lower()

    if any(x in t for x in ["love","miss","good"]):
        reward += 2
    elif any(x in t for x in ["bad","ignore","hate"]):
        reward -= 2

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"reward": reward}},
        upsert=True
    )

# ---------------- CUSTOM DATASET ----------------

def learn_dataset(user_text, reply):

    if len(user_text) > 3 and len(reply) > 3:
        dataset_col.insert_one({
            "user": user_text.lower(),
            "reply": reply
        })

def get_dataset_reply(user_text):

    data = dataset_col.find_one({"user": user_text.lower()})
    if data:
        return data["reply"]

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
- sometimes incomplete sentence

BEHAVIOR:
- real girl like
- sometimes ignore
- sometimes tease
- sometimes emotional
"""

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

    attach = mem.get("reward", 0)

    t = user_text.lower()

    if t in ["hmm","ok","hn","acha"]:
        return random.choice(["hmm","acha","hn"])

    if attach > 20:
        return random.choice([
            "tumse baat acchi lagti h",
            "tum thode special ho"
        ])

    if attach > 5:
        return random.choice([
            "tum bhi na 😏",
            "acha ji"
        ])

    return None

# ---------------- AI ----------------

def ai_reply(user_text, history, mem):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    prompt = f"""
{PERSONALITY}

Life:
{real_life()}

CHAT:
{context}

User: {user_text}

RULES:
- continue topic
- no repetition
- short reply
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

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    update_rl(chat_id, user_text)

    mem = get_memory(chat_id)

    # 1️⃣ dataset
    dataset_reply = get_dataset_reply(user_text)

    if dataset_reply:
        reply = dataset_reply

    else:
        # 2️⃣ brain
        decision = brain(user_text, mem)

        if decision:
            reply = decision
        else:
            # 3️⃣ AI
            reply = ai_reply(user_text, history, mem)

    time.sleep(random.uniform(1,2))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    send(chat_id, reply)

    # save history
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

    # learn dataset
    learn_dataset(user_text, reply)

    # auto msg trigger
    if random.random() < 0.3:
        auto_message()

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra AI Ultimate Running"
