import os, requests, random, time, re, threading
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['zayra_ai']

history_col = db['chat']
memory_col = db['memory']
profile_col = db['profile']
tasks_col = db['tasks']
mistake_col = db['mistakes']

# -------- TIME --------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

# -------- MEMORY --------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, user_text):

    mem = get_memory(chat_id)

    attach = mem.get("attachment", 30)
    mood = mem.get("mood", "normal")
    evolve = mem.get("evolve", 0)

    t = user_text.lower()

    if any(x in t for x in ["love","miss","care"]):
        attach += 3
        evolve += 1

    if "ignore" in t:
        attach -= 4
        mood = "sad"

    if "sorry" in t:
        mood = "soft"

    attach = max(0, min(100, attach))

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "attachment": attach,
            "mood": mood,
            "evolve": evolve
        }},
        upsert=True
    )

# -------- LEARNING --------
def learning_engine(chat_id, text):

    if "like" in text.lower() or "pasand" in text.lower():
        profile_col.update_one(
            {"chat_id": chat_id},
            {"$push": {"likes": text}},
            upsert=True
        )

def recall_profile(chat_id):
    data = profile_col.find_one({"chat_id": chat_id})
    if data and "likes" in data:
        return f"tumhe {random.choice(data['likes'])} pasand hai na"
    return None

# -------- MISTAKE --------
def learn_mistake(chat_id, text):
    if "galat" in text.lower():
        mistake_col.insert_one({"chat_id": chat_id, "text": text})
        return True
    return False

# -------- TASK --------
def save_task(chat_id, text):
    match = re.search(r'(\d{1,2}) ?baje', text.lower())
    if not match:
        return False

    hour = int(match.group(1))

    t = now_ist().replace(hour=hour, minute=0, second=0)
    if t < now_ist():
        t += timedelta(days=1)

    tasks_col.insert_one({
        "chat_id": chat_id,
        "time": t,
        "done": False
    })

    return True

def run_tasks():
    now = now_ist()
    for t in tasks_col.find({"done": False, "time": {"$lte": now}}):
        send(t["chat_id"], "uth jao bola tha na")
        send(t["chat_id"], "abhi bhi so rahe ho kya")
        tasks_col.update_one({"_id": t["_id"]}, {"$set": {"done": True}})

# -------- STYLE --------
def get_style():
    return random.choice(["romantic","deep","teasing","soft","playful"])

# -------- CREATIVE --------
def creative_engine(text):

    t = text.lower()

    if any(x in t for x in ["shayari","sher","ghazal","poetry"]):

        style = get_style()

        prompt = f"""
Write 1 short Hinglish shayari.

STYLE: {style}

RULES:
- max 2 lines
- emotional
- no emoji
- unique
"""

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model":"llama-3.3-70b-versatile",
                "messages":[{"role":"user","content":prompt}],
                "temperature":1,
                "max_tokens":60
            }
        )

        if r.status_code == 200:
            return r.json()['choices'][0]['message']['content']

    if "joke" in t:
        return random.choice([
            "tum itne serious kyun rehte ho",
            "tumhari wajah se main confuse ho jati hu"
        ])

    return None

# -------- DECISION --------
def decision_engine(chat_id):

    mem = get_memory(chat_id)

    if mem.get("mood") == "sad":
        return "abhi mood thoda off hai"

    if mem.get("attachment",30) > 80:
        return random.choice([
            "tum important ho",
            "tumse baat acchi lagti hai"
        ])

    return None

# -------- AI --------
def ai_reply(text, history):

    context = ""
    for m in history:
        role = "User" if m["role"]=="user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    prompt = f"""
You are Zayra.

- hinglish
- max 8 words
- no emoji
- natural
- real girl behavior
- continue conversation

CHAT:
{context}

User: {text}
"""

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model":"llama-3.3-70b-versatile",
            "messages":[{"role":"user","content":prompt}],
            "temperature":0.9,
            "max_tokens":50
        }
    )

    if r.status_code == 200:
        return r.json()['choices'][0]['message']['content']

    return "hmm"

# -------- DELAY --------
def human_delay(chat_id, reply):

    time.sleep(random.uniform(0.5,1.5))

    requests.post(f"{TELEGRAM_API}/sendChatAction",
                  json={"chat_id": chat_id, "action": "typing"})

    if len(reply.split()) <= 5:
        time.sleep(random.uniform(2,4))
    else:
        time.sleep(random.uniform(4,7))

# -------- CONTINUE --------
def continue_convo(chat_id):

    if random.random() > 0.4:
        return

    time.sleep(random.uniform(2,4))

    send(chat_id, random.choice([
        "tumhe kaisa laga",
        "tum bhi kuch bolo",
        "waise tum itne chup kyun ho"
    ]))

# -------- SELF --------
def smart_self_message(chat_id):

    mem = get_memory(chat_id)

    if mem.get("attachment",30) > 70:
        msg = random.choice([
            "tum yaad aa rahe ho",
            "baat karne ka mann tha"
        ])
    else:
        msg = random.choice([
            "aaj kya kar rahe ho",
            "aaj ka plan kya hai"
        ])

    send(chat_id, msg)

# -------- AUTO --------
def auto_loop():
    while True:
        time.sleep(random.randint(180,600))
        run_tasks()
        smart_self_message(ALLOWED_USER_ID)

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

    text = msg.get("text")
    if not text:
        return {"ok": True}

    run_tasks()

    if learn_mistake(chat_id, text):
        send(chat_id, "ok dobara nahi karungi")
        return {"ok": True}

    if save_task(chat_id, text):
        send(chat_id, "ok yaad rahega")
        return {"ok": True}

    learning_engine(chat_id, text)

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    reply = decision_engine(chat_id)

    if not reply:
        reply = creative_engine(text)

    if not reply:
        reply = ai_reply(text, history)

    human_delay(chat_id, reply)
    send(chat_id, reply)

    continue_convo(chat_id)

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

    update_memory(chat_id, text)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Ultra AGI Creative Running"

threading.Thread(target=auto_loop, daemon=True).start()
