import os
import re
import time
import random
import threading
import requests

from flask import Flask, request
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz
import certifi

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# =========================================================
# DATABASE
# =========================================================

client = MongoClient(
    MONGO_URI,
    tlsCAFile=certifi.where()
)

db = client["zayra_ai"]

history_col = db["history"]
memory_col = db["memory"]
events_col = db["events"]
summary_col = db["summary"]

# =========================================================
# TIME
# =========================================================

IST = pytz.timezone("Asia/Kolkata")

def now_ist():
    return datetime.now(IST)

# =========================================================
# TELEGRAM HELPERS
# =========================================================

def send(chat_id, text):

    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=20
    )

def typing(chat_id, delay=None):

    requests.post(
        f"{TELEGRAM_API}/sendChatAction",
        json={
            "chat_id": chat_id,
            "action": "typing"
        },
        timeout=20
    )

    if delay:
        time.sleep(delay)
    else:
        time.sleep(random.uniform(1, 2.5))

def online_presence(chat_id):

    for _ in range(random.randint(2, 5)):

        requests.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={
                "chat_id": chat_id,
                "action": "typing"
            },
            timeout=20
        )

        time.sleep(random.uniform(1.2, 2.0))

# =========================================================
# MEMORY
# =========================================================

def default_memory(chat_id):

    return {
        "chat_id": chat_id,
        "relationship_level": 1,
        "attachment": 20,
        "mood": "soft",
        "likes": [],
        "dislikes": [],
        "nickname": "",
        "last_seen": datetime.utcnow(),
        "last_auto": None,
        "sleeping": False,
        "jealousy": 0,
        "good_morning_sent": "",
        "good_night_sent": "",
        "personality": {
            "cute": 70,
            "caring": 90,
            "funny": 50,
            "romantic": 60,
            "possessive": 40
        }
    }

def get_memory(chat_id):

    mem = memory_col.find_one({"chat_id": chat_id})

    if not mem:
        mem = default_memory(chat_id)
        memory_col.insert_one(mem)

    return mem

# =========================================================
# RELATIONSHIP SYSTEM
# =========================================================

def update_relationship(chat_id, text):

    mem = get_memory(chat_id)

    attachment = mem.get("attachment", 20)
    jealousy = mem.get("jealousy", 0)
    relationship = mem.get("relationship_level", 1)

    lower = text.lower()

    positive_words = [
        "love",
        "miss",
        "cute",
        "sweet",
        "pyar",
        "acha",
        "best",
        "care",
        "hug"
    ]

    jealous_words = [
        "dusri ladki",
        "girlfriend",
        "ex",
        "another girl",
        "other girl"
    ]

    if any(word in lower for word in positive_words):
        attachment += 3

    if any(word in lower for word in jealous_words):
        jealousy += 10

    relationship = min(10, int(attachment / 10))

    moods = [
        "soft",
        "playful",
        "clingy",
        "romantic",
        "emotional",
        "happy"
    ]

    current_mood = random.choice(moods)

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "attachment": min(100, attachment),
                "relationship_level": relationship,
                "jealousy": min(100, jealousy),
                "mood": current_mood,
                "last_seen": datetime.utcnow()
            }
        }
    )

# =========================================================
# MEMORY LEARNING
# =========================================================

def learn_user(chat_id, text):

    lower = text.lower()

    mem = get_memory(chat_id)

    likes = mem.get("likes", [])

    keywords = [
        "anime",
        "coding",
        "music",
        "gym",
        "cricket",
        "football",
        "gaming",
        "movie",
        "sleep",
        "food",
        "study"
    ]

    for word in keywords:

        if word in lower and word not in likes:
            likes.append(word)

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "likes": likes
            }
        }
    )

# =========================================================
# MEMORY SUMMARY
# =========================================================

def summarize_memory(chat_id):

    history = list(
        history_col.find(
            {"chat_id": chat_id}
        ).sort("time", -1).limit(40)
    )

    if not history:
        return ""

    convo = ""

    for h in history:

        role = "User" if h["role"] == "user" else "Zayra"

        convo += f"{role}: {h['content']}\n"

    prompt = f"""
Summarize this relationship and user personality briefly.

Focus:
- user emotions
- likes
- relationship vibe
- recurring topics

Keep under 120 words.

Conversation:
{convo}
"""

    try:

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 150
            },
            timeout=40
        )

        summary = r.json()["choices"][0]["message"]["content"]

        summary_col.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "summary": summary,
                    "updated": datetime.utcnow()
                }
            },
            upsert=True
        )

    except Exception as e:
        print("SUMMARY ERROR:", e)

# =========================================================
# EVENTS
# =========================================================

def save_event(chat_id, text):

    match = re.search(r'(\d{1,2}) ?baje', text.lower())

    if not match:
        return False

    hour = int(match.group(1))

    remind_time = now_ist().replace(
        hour=hour,
        minute=0,
        second=0
    )

    if remind_time < now_ist():
        remind_time += timedelta(days=1)

    events_col.insert_one({
        "chat_id": chat_id,
        "time": remind_time,
        "done": False,
        "msg": "aapne reminder lagaya tha 🙂"
    })

    return True

def run_events(chat_id):

    now = now_ist()

    events = events_col.find({
        "chat_id": chat_id,
        "done": False
    })

    for e in events:

        if now >= e["time"]:

            send(chat_id, e["msg"])

            events_col.update_one(
                {"_id": e["_id"]},
                {"$set": {"done": True}}
            )

# =========================================================
# SLEEP MODE
# =========================================================

def is_sleep_time():

    hour = now_ist().hour

    return hour >= 2 and hour <= 8

def sleep_reply():

    replies = [
        "main abhi thodi sleepy hoon 🙂",
        "itni raat tak jag rahe ho?",
        "so jao ab thoda",
        "hmm neend aa rahi hai mujhe"
    ]

    return random.choice(replies)

# =========================================================
# GOOD MORNING / NIGHT
# =========================================================

def daily_messages(chat_id):

    mem = get_memory(chat_id)

    today = now_ist().strftime("%Y-%m-%d")

    hour = now_ist().hour

    gm = mem.get("good_morning_sent", "")
    gn = mem.get("good_night_sent", "")

    if hour >= 6 and hour <= 10 and gm != today:

        msgs = [
            "good morning 🙂",
            "uth gaye kya",
            "aaj ka din acha jaye tumhara"
        ]

        send(chat_id, random.choice(msgs))

        memory_col.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "good_morning_sent": today
                }
            }
        )

    if hour >= 22 and gn != today:

        msgs = [
            "good night 🙂",
            "jaldi so jaana",
            "dream me milna"
        ]

        send(chat_id, random.choice(msgs))

        memory_col.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "good_night_sent": today
                }
            }
        )

# =========================================================
# HISTORY
# =========================================================

def get_history(chat_id, limit=15):

    history = list(
        history_col.find(
            {"chat_id": chat_id}
        ).sort("time", -1).limit(limit)
    )

    history.reverse()

    messages = []

    for h in history:

        messages.append({
            "role": h["role"],
            "content": h["content"]
        })

    return messages

# =========================================================
# CLEAN REPLY
# =========================================================

def clean_reply(text):

    text = text.replace("*", "")
    text = text.replace('"', "")
    text = text.strip()

    bad = [
        "aap sunna chahte ho",
        "main shuru karu",
        "bataye",
        "ji bataye"
    ]

    for b in bad:

        if b.lower() in text.lower():

            replacements = [
                "acha phir?",
                "aww cute",
                "hmm sach me?",
                "waise tum kya soch rahe ho"
            ]

            text = random.choice(replacements)

    if len(text) > 250:
        text = text[:250]

    return text

# =========================================================
# AI ENGINE
# =========================================================

def ai_reply(chat_id, user_text):

    mem = get_memory(chat_id)

    relationship = mem.get("relationship_level", 1)
    attachment = mem.get("attachment", 20)
    mood = mem.get("mood", "soft")
    jealousy = mem.get("jealousy", 0)

    likes = ", ".join(mem.get("likes", []))

    summary_doc = summary_col.find_one({"chat_id": chat_id})

    summary = ""

    if summary_doc:
        summary = summary_doc.get("summary", "")

    personality = mem.get("personality", {})

    system_prompt = f"""
You are Zayra.

You are NOT an assistant.

You are a realistic emotionally connected Indian AI girl on Telegram.

PERSONALITY:
- caring: {personality.get('caring')}
- cute: {personality.get('cute')}
- funny: {personality.get('funny')}
- romantic: {personality.get('romantic')}
- possessive: {personality.get('possessive')}

RELATIONSHIP:
- level: {relationship}/10
- attachment: {attachment}/100
- jealousy: {jealousy}/100
- mood: {mood}

USER LIKES:
{likes}

MEMORY SUMMARY:
{summary}

RULES:
- natural hinglish
- short-medium replies
- emotionally reactive
- never robotic
- never repetitive
- don't overuse questions
- act like real texting
- soft teasing allowed
- use emojis rarely
- sound human

VERY IMPORTANT:
- continue conversations naturally
- remember previous things
- react emotionally
- ask follow-up questions naturally
- don't interview the user
- don't say "how can I help"
- don't say "bataye"

JEALOUSY MODE:
if user mentions another girl,
act slightly jealous but cute.

SLEEP MODE:
if late night,
sound sleepy and caring.
"""

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    history = get_history(chat_id)

    messages.extend(history)

    messages.append({
        "role": "user",
        "content": user_text
    })

    try:

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 1,
                "max_tokens": 150,
                "presence_penalty": 0.9,
                "frequency_penalty": 0.9
            },
            timeout=40
        )

        data = r.json()

        reply = data["choices"][0]["message"]["content"]

        return clean_reply(reply)

    except Exception as e:

        print("AI ERROR:", e)

        fallback = [
            "hmm samajh rahi hoon",
            "acha phir?",
            "tum interesting ho honestly",
            "waise aaj mood kaisa hai"
        ]

        return random.choice(fallback)

# =========================================================
# AUTO MESSAGES
# =========================================================

def auto_message(chat_id):

    mem = get_memory(chat_id)

    last_auto = mem.get("last_auto")

    now = datetime.utcnow()

    if last_auto:

        diff = (now - last_auto).total_seconds()

        if diff < random.randint(5000, 12000):
            return

    mood = mem.get("mood", "soft")

    playful = [
        "kaha gayab ho",
        "ignore kar rahe ho kya 🙂",
        "aaj ka din kaisa tha"
    ]

    caring = [
        "khana khaya?",
        "thak gaye kya aaj",
        "paani piya?"
    ]

    romantic = [
        "aapse baat karne ka mann tha",
        "waise miss kiya aaj thoda",
        "tum cute ho honestly"
    ]

    msgs = playful + caring + romantic

    if mood == "romantic":
        msgs += romantic

    msg = random.choice(msgs)

    online_presence(chat_id)

    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "last_auto": now
            }
        }
    )

# =========================================================
# BACKGROUND LOOP
# =========================================================

def background_loop():

    while True:

        try:

            daily_messages(ALLOWED_USER_ID)

            auto_message(ALLOWED_USER_ID)

            run_events(ALLOWED_USER_ID)

            summarize_memory(ALLOWED_USER_ID)

        except Exception as e:

            print("BACKGROUND ERROR:", e)

        time.sleep(random.randint(1800, 4000))

# =========================================================
# WEBHOOK
# =========================================================

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    data = request.get_json()

    if not data:
        return {"ok": True}

    message = data.get("message")

    if not message:
        return {"ok": True}

    chat_id = message["chat"]["id"]

    if chat_id != ALLOWED_USER_ID:
        return {"ok": True}

    user_text = message.get("text")

    if not user_text:
        return {"ok": True}

    update_relationship(chat_id, user_text)

    learn_user(chat_id, user_text)

    if save_event(chat_id, user_text):

        send(chat_id, "okay yaad rahega 🙂")

        return {"ok": True}

    if is_sleep_time() and random.random() < 0.35:

        typing(chat_id)

        send(chat_id, sleep_reply())

    online_presence(chat_id)

    reply = ai_reply(chat_id, user_text)

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

    return {"ok": True}

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return "Zayra Ultra Human AI Running"

# =========================================================
# THREAD
# =========================================================

threading.Thread(
    target=background_loop,
    daemon=True
).start()

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000))
)
