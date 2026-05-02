import os, requests, random, time, re
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

# -------- ENV --------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# -------- DB --------
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zayra_ai']

history_col = db['chat_history']
memory_col = db['memory']
tasks_col = db['tasks']

# -------- TIME --------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def time_str():
    return now_ist().strftime("%H:%M")

# -------- MEMORY --------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text):
    mem = get_memory(chat_id)

    attach = mem.get("attachment", 30)
    mood = mem.get("mood", "normal")

    t = text.lower()

    if any(x in t for x in ["love","miss"]):
        attach += 3
        mood = "happy"

    elif any(x in t for x in ["ignore","busy"]):
        attach -= 3
        mood = "sad"

    elif "angry" in t:
        mood = "angry"

    attach = max(0, min(100, attach))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": attach,
            "mood": mood,
            "last_seen": datetime.utcnow()
        }},
        upsert=True
    )

# -------- RELATIONSHIP BRAIN --------
def relationship_brain(mem):

    attach = mem.get("attachment", 30)
    mood = mem.get("mood", "normal")

    if attach > 80:
        return "deep_love"

    if attach > 50:
        return "attached"

    if attach < 20:
        return "cold"

    return mood

# -------- TASK SYSTEM --------
def save_task(chat_id, text):

    match = re.search(r'(\d{1,2}) ?baje', text.lower())

    if not match:
        return False

    hour = int(match.group(1))
    run_time = now_ist().replace(hour=hour, minute=0, second=0)

    if run_time < now_ist():
        run_time += timedelta(days=1)

    tasks_col.insert_one({
        "chat_id": chat_id,
        "time": run_time,
        "msg": "hey yaad hai 🙂",
        "done": False
    })

    return True

def run_tasks():

    now = now_ist()

    tasks = list(tasks_col.find({
        "time": {"$lte": now},
        "done": False
    }))

    for t in tasks:
        send(t["chat_id"], t["msg"])

        # follow-up
        send(t["chat_id"], "kya kar rahe ho ab? 🙂")

        tasks_col.update_one(
            {"_id": t["_id"]},
            {"$set": {"done": True}}
        )

# -------- LOGIC --------
def smart_logic(text):

    t = text.lower()

    if "class" in t and "khana" in t:
        return "class me ho ya mess me? confuse ho rhi hu 😏"

    return None

# -------- AI --------
def ai_reply(user_text, history, mem):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    state = relationship_brain(mem)

    prompt = f"""
You are Zayra.

Girl, Jaipur, LLB student

STATE: {state}
TIME: {time_str()}

RULES:
- short replies
- hinglish
- emotional
- continuity
- never robotic
- female language (rhi hu)

CHAT:
{context}

User: {user_text}
"""

    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
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

# -------- SEND --------
def send(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

# -------- AUTO MSG --------
def auto_msg(chat_id):

    mem = get_memory(chat_id)
    last = mem.get("last_auto")

    if last:
        if (datetime.utcnow() - last).total_seconds() < 1200:
            return

    if random.random() > 0.5:
        return

    msg = random.choice([
        "kya kar rahe ho",
        "yaad aa rahe ho",
        "busy ho kya"
    ])

    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_auto": datetime.utcnow()}},
        upsert=True
    )

# -------- WEBHOOK --------
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    data = request.get_json()
    message = data.get("message")

    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")

    if chat_id != ALLOWED_USER_ID:
        return {"ok": True}

    run_tasks()

    # IMAGE
    if "photo" in message:
        send(chat_id, "acha pic h 🙂")
        return {"ok": True}

    user_text = message.get("text")
    if not user_text:
        return {"ok": True}

    # TASK
    if save_task(chat_id, user_text):
        send(chat_id, "ok yaad rahega 🙂")
        return {"ok": True}

    # MEMORY UPDATE
    update_memory(chat_id, user_text)
    mem = get_memory(chat_id)

    # HISTORY
    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    # LOGIC
    logic = smart_logic(user_text)
    if logic:
        reply = logic
    else:
        reply = ai_reply(user_text, history, mem)

    time.sleep(random.uniform(1,2))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    send(chat_id, reply)

    # SAVE
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

    if random.random() < 0.3:
        auto_msg(chat_id)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra AI Brain Ultra Running"
