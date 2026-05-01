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

# ---------------- DB ----------------

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
    elif any(x in user_text.lower() for x in ["love","miss","cute"]):
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

def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

# ---------------- TIME ----------------

def get_time_mood():
    h = datetime.now().hour
    if h < 12:
        return "morning"
    elif h < 18:
        return "day"
    else:
        return "night"

# ---------------- EMOJI ----------------

def handle_emoji(text, attach):

    if "❤️" in text:
        return random.choice([
            "acha 😏",
            "mere liye tha kya",
            "hmm samajh gyi"
        ])

    if "😂" in text:
        return random.choice([
            "pagal ho kya 😂",
            "itna funny kya h",
            "hassi aa rhi h tumhe"
        ])

    if "😢" in text or "😭" in text:
        return random.choice([
            "kya hua",
            "btao na",
            "seriously kya hua?"
        ])

    if "😒" in text:
        return random.choice([
            "attitude kyu",
            "ab kya hua",
            "theek ho?"
        ])

    return None

# ---------------- FLIRT ----------------

def flirt_reply(attach):

    if attach < 40:
        return random.choice(["acha 😅", "hmm", "theek h"])

    elif attach < 80:
        return random.choice([
            "tum bhi na 😏",
            "acha ji",
            "zyada mat bolo"
        ])

    else:
        return random.choice([
            "sirf bol rahe ho ya sach me 😏",
            "tum thode special ho",
            "acha lagta h tumse baat karna"
        ])

# ---------------- IMAGE (FREE) ----------------

def image_reply(chat_id):

    mem = get_memory(chat_id)
    count = mem.get("img_count", 0) + 1

    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"img_count": count}},
        upsert=True
    )

    replies = [
        "acha lag rahe ho 😏",
        "pose to hero wala h",
        "ye pic kab ki h?",
        "selfie mood me ho aaj",
        "kaha click ki ye"
    ]

    if count > 2:
        replies.append("tum pics bhejna pasand karte ho na 😏")

    return random.choice(replies)

# ---------------- AI ----------------

def ai_reply(user_text, history, attach):

    context = ""
    for m in history:
        role = "User" if m["role"] == "user" else "Zayra"
        context += f"{role}: {m['content']}\n"

    time_mood = get_time_mood()

    prompt = f"""
You are Zayra (Jaipur, LLB student).

Time: {time_mood}
Attachment: {attach}

CHAT:
{context}

User: {user_text}

RULES:

- Hinglish
- short replies
- natural texting
- no robotic tone
- continue context

BEHAVIOR:
- morning → sleepy
- night → emotional
- high attachment → soft + possessive

Examples:
"hmm"
"acha"
"tum bhi na"
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

    # 📸 IMAGE
    if "photo" in message:
        reply = image_reply(chat_id)
        send(chat_id, reply)
        save(chat_id, "assistant", reply)
        return {"ok": True}

    user_text = message.get("text")

    if not user_text:
        return {"ok": True}

    attach = update_memory(chat_id, user_text)

    # 😶 emoji
    emoji_res = handle_emoji(user_text, attach)
    if emoji_res:
        send(chat_id, emoji_res)
        save(chat_id, "assistant", emoji_res)
        return {"ok": True}

    # 😏 flirt
    if any(x in user_text.lower() for x in ["love","cute","miss"]):
        reply = flirt_reply(attach)
        send(chat_id, reply)
        save(chat_id, "assistant", reply)
        return {"ok": True}

    history = get_history(chat_id)

    time.sleep(random.uniform(0.8,2))

    requests.post(f"{TELEGRAM_API}/sendChatAction", json={
        "chat_id": chat_id,
        "action": "typing"
    })

    reply = ai_reply(user_text, history, attach)

    # short control
    if user_text.lower() in ["hmm","ok","hn","acha"]:
        reply = random.choice(["hmm", "acha", "hn"])

    # human randomness
    if random.random() < 0.2:
        reply = reply.lower()

    if random.random() < 0.15:
        reply = reply[:len(reply)//2]

    send(chat_id, reply)

    save(chat_id, "user", user_text)
    save(chat_id, "assistant", reply)

    return {"ok": True}

@app.route("/")
def home():
    return "Zayra Final AI Running"
