import os, requests, random, time, threading
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime
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

# -------- TIME --------
def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def is_sleep_time():
    return 0 <= now_ist().hour <= 5

# -------- MEMORY --------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text):
    mem = get_memory(chat_id)
    now = datetime.utcnow()

    last = mem.get("last_user_time")
    gap = 0
    if last:
        gap = (now - last).total_seconds()

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "last_user_time": now,
            "last_gap": gap
        }},
        upsert=True
    )

# -------- DOUBLE MESSAGE --------
def merge_messages(chat_id, new_text):

    last = history_col.find_one(
        {"chat_id": chat_id, "role": "user"},
        sort=[("time",-1)]
    )

    if not last:
        return new_text

    gap = (datetime.utcnow() - last["time"]).total_seconds()

    if gap < 15:
        return last["content"] + " " + new_text

    return new_text

# -------- SHORT MSG --------
def handle_short(original_text):

    t = original_text.lower().strip()

    if t in ["hmm","ok","hn","acha"]:
        return random.choice([
            "bas itna hi",
            "kuch bolna hai kya",
            "itna short kyun"
        ])

    return None

# -------- THINKING ENGINE --------
def thinking_engine(text):

    if len(text.split()) < 3:
        if random.random() < 0.3:
            return random.choice(["hmm","acha"])

    return None

# -------- AI --------
def ai_reply(text, history):

    context = ""
    for m in history:
        role = "User" if m["role"]=="user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    tone = "normal"
    if is_sleep_time():
        tone = "sleepy"

    prompt = f"""
You are Zayra (real indian girl)

STYLE:
- hinglish
- natural
- mostly short replies (5-12 words)
- sometimes slightly longer if emotional
- no emoji
- no repetition
- think before replying

TONE: {tone}

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
            "max_tokens":80
        }
    )

    if r.status_code == 200:
        return r.json()['choices'][0]['message']['content']

    return "hmm"

# -------- CONTROL --------
def control_reply(reply):

    words = reply.split()

    if len(words) > 12:
        reply = " ".join(words[:10])

    if len(words) < 2:
        return "hmm"

    return reply

# -------- REPEAT CHECK --------
def is_repeated(chat_id, reply):

    last = history_col.find_one(
        {"chat_id": chat_id, "role": "assistant"},
        sort=[("time",-1)]
    )

    if not last:
        return False

    return last["content"].lower() == reply.lower()

# -------- SELF MESSAGE --------
def smart_self_message(chat_id):

    if is_sleep_time():
        return

    mem = get_memory(chat_id)
    now = datetime.utcnow()

    last_self = mem.get("last_self")
    last_user = mem.get("last_user_time")

    if last_user and (now - last_user).total_seconds() < 1800:
        return

    gap = random.randint(3600,28800)

    if last_self and (now - last_self).total_seconds() < gap:
        return

    if random.random() < 0.5:
        return

    msgs = [
        "kya kar rahe ho",
        "kaise ho",
        "khana khaya kya",
        "busy ho kya",
        "arey mujhe bhi yaad kar lo"
    ]

    msg = random.choice(msgs)

    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_self": now}},
        upsert=True
    )

# -------- AUTO LOOP --------
def auto_loop():
    while True:
        time.sleep(random.randint(600,1800))
        smart_self_message(ALLOWED_USER_ID)

# -------- SEND --------
def send(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

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

    original_text = msg.get("text")

    if not original_text:
        return {"ok": True}

    update_memory(chat_id, original_text)

    merged_text = merge_messages(chat_id, original_text)

    history = list(history_col.find({"chat_id": chat_id})
                   .sort("time",-1).limit(10))
    history.reverse()

    # -------- PIPELINE --------
    reply = handle_short(original_text)

    if not reply:
        reply = thinking_engine(merged_text)

    if not reply:
        reply = ai_reply(merged_text, history)

    reply = control_reply(reply)

    if is_repeated(chat_id, reply):
        reply = "hmm kuch aur bolte hain"

    time.sleep(random.uniform(2,5))
    send(chat_id, reply)

    # SAVE ONLY MERGED
    history_col.insert_one({
        "chat_id": chat_id,
        "role": "user",
        "content": merged_text,
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
    return "Zayra v10 True Human AI Running"

threading.Thread(target=auto_loop, daemon=True).start()
