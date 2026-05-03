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

history_col = db['chat']
memory_col = db['memory']
tasks_col = db['tasks']
important_col = db['important']

# -------- TIME --------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

# -------- HUMAN TYPING SYSTEM --------

def human_behavior_mode():
    r = random.random()
    if r < 0.2:
        return "instant"
    elif r < 0.4:
        return "slow"
    return "normal"

def human_typing_delay(chat_id, reply):

    words = len(reply.split())

    # seen delay
    time.sleep(random.uniform(0.5, 1.5))

    # typing indicator
    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    # delay based on length
    if words <= 5:
        delay = random.uniform(2, 5)
    elif words <= 10:
        delay = random.uniform(4, 7)
    else:
        delay = random.uniform(6, 10)

    time.sleep(delay)

# -------- MEMORY --------

def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text):
    mem = get_memory(chat_id)

    attach = mem.get("attachment", 30)
    mood = mem.get("mood", "normal")
    mood_lock = mem.get("mood_lock", 0)

    t = text.lower()

    if mood_lock <= 0:
        if "miss" in t or "love" in t:
            mood = "happy"
            mood_lock = 3
            attach += 2

        elif "ignore" in t or "busy" in t:
            mood = "sad"
            mood_lock = 3
            attach -= 2
    else:
        mood_lock -= 1

    attach = max(0, min(100, attach))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": attach,
            "mood": mood,
            "mood_lock": mood_lock
        }},
        upsert=True
    )

# -------- MEMORY RECALL --------

def recall(history):
    msgs = [m["content"] for m in history if m["role"] == "user"]
    if len(msgs) >= 2:
        return msgs[-2]
    return ""

# -------- IMPORTANT MEMORY --------

def save_important(chat_id, text):
    if len(text) < 5:
        return
    if any(x in text.lower() for x in ["name","city","like","college"]):
        important_col.insert_one({
            "chat_id": chat_id,
            "text": text
        })

def get_important(chat_id):
    data = list(important_col.find({"chat_id": chat_id}).limit(5))
    return " ".join([d["text"] for d in data])

# -------- LOGIC LAYER --------

def logic_layer(text):
    t = text.lower()

    if "class" in t and "khana" in t:
        return "class me ho ya kha rahe ho 😏"

    if len(t) < 3:
        return random.choice(["hmm", "acha", "hn"])

    return None

# -------- EMOTION LAYER --------

def emotion_layer(mem):

    mood = mem.get("mood", "normal")
    attach = mem.get("attachment", 30)

    if mood == "sad":
        return random.choice(["acha thik", "jo tumhe sahi lage"])

    if attach > 70:
        return random.choice(["tumse baat acchi lagti h", "tum special ho"])

    if attach < 20:
        return random.choice(["hmm", "acha"])

    return None

# -------- AI --------

def ai_reply(user_text, history, mem):

    context = ""
    for m in history:
        role = "User" if m["role"]=="user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    prompt = f"""
You are Zayra.

- real girl
- short replies only
- hinglish
- max 8 words

Memory: {recall(history)}
Important: {get_important(ALLOWED_USER_ID)}

CHAT:
{context}

User: {user_text}
"""

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model":"llama-3.3-70b-versatile",
            "messages":[{"role":"user","content":prompt}],
            "temperature":0.8,
            "max_tokens":40
        }
    )

    if r.status_code == 200:
        return r.json()['choices'][0]['message']['content']

    return "hmm"

# -------- CONTROL --------

def control(reply):
    words = reply.split()
    if len(words) > 8:
        reply = " ".join(words[:6])
    return reply

# -------- SELF MESSAGE --------

def self_msg(chat_id):

    mem = get_memory(chat_id)
    last = mem.get("self")
    now = datetime.utcnow()

    if last and (now-last).total_seconds() < 900:
        return

    if random.random() > 0.3:
        return

    msg = random.choice([
        "kya kar rahe ho",
        "yaad aa rahe ho",
        "busy ho kya",
        "acha suno"
    ])

    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"self": now}},
        upsert=True
    )

# -------- TASK --------

def save_task(chat_id, text):

    m = re.search(r'(\d{1,2}) ?baje', text.lower())
    if not m:
        return False

    hour = int(m.group(1))

    t = now_ist().replace(hour=hour, minute=0, second=0)
    if t < now_ist():
        t += timedelta(days=1)

    tasks_col.insert_one({
        "chat_id": chat_id,
        "time": t,
        "msg": "yaad hai 🙂",
        "done": False
    })

    return True

def run_tasks():

    now = now_ist()

    tasks = list(tasks_col.find({"done": False, "time": {"$lte": now}}))

    for t in tasks:
        send(t["chat_id"], t["msg"])
        send(t["chat_id"], "ab kya kar rahe ho?")
        tasks_col.update_one({"_id": t["_id"]}, {"$set": {"done": True}})

# -------- SEND --------

def send(chat_id, text):
    requests.post(f"{TELEGRAM_API}/sendMessage",
                  json={"chat_id": chat_id, "text": text})

# -------- WEBHOOK --------

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    data = request.get_json()
    msg = data.get("message")
    if not msg:
        return {"ok": True}

    chat_id = msg["chat"]["id"]
    if chat_id != ALLOWED_USER_ID:
        return {"ok": True}

    run_tasks()
    self_msg(chat_id)

    text = msg.get("text")
    if not text:
        return {"ok": True}

    if save_task(chat_id, text):
        send(chat_id, "ok yaad rahega 🙂")
        return {"ok": True}

    update_memory(chat_id, text)
    save_important(chat_id, text)

    mem = get_memory(chat_id)

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time", -1).limit(10))
    history.reverse()

    # -------- DECISION PIPELINE --------

    reply = logic_layer(text)

    if not reply:
        reply = emotion_layer(mem)

    if not reply:
        reply = ai_reply(text, history, mem)

    reply = control(reply)

    # -------- HUMAN DELAY SYSTEM --------

    mode = human_behavior_mode()

    if mode == "instant":
        pass
    elif mode == "slow":
        time.sleep(random.uniform(3, 6))
        human_typing_delay(chat_id, reply)
    else:
        human_typing_delay(chat_id, reply)

    send(chat_id, reply)

    history_col.insert_one({
        "chat_id": chat_id,
        "role": "user",
        "content": text,
        "time": datetime.utcnow()
    })

    history_col.insert_one({
        "chat_id": chat_id,
        "role": "assistant",
        "content": reply,
        "time": datetime.utcnow()
    })

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra v7 Ultra Human Typing Running 🔥"
