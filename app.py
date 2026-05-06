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
# TELEGRAM
# =========================================================

def send(chat_id, text):

    if not text:
        return

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
        time.sleep(random.uniform(1.0, 2.2))

# =========================================================
# REALISTIC ONLINE PRESENCE
# =========================================================

def online_presence(chat_id):

    loops = random.randint(1, 3)

    for _ in range(loops):

        requests.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={
                "chat_id": chat_id,
                "action": "typing"
            },
            timeout=20
        )

        time.sleep(random.uniform(0.8, 1.8))

# =========================================================
# MEMORY
# =========================================================

def default_memory(chat_id):

    return {
        "chat_id": chat_id,
        "attachment": 20,
        "relationship_level": 1,
        "mood": "soft",
        "likes": [],
        "nickname": "",
        "jealousy": 0,
        "sleeping": False,
        "last_auto": None,
        "last_seen": datetime.utcnow(),
        "good_morning_sent": "",
        "good_night_sent": "",
        "conversation_mode": "normal",
        "personality": {
            "cute": 80,
            "caring": 90,
            "funny": 60,
            "romantic": 70,
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
# RELATIONSHIP ENGINE
# =========================================================

def update_relationship(chat_id, text):

    mem = get_memory(chat_id)

    attachment = mem.get("attachment", 20)
    jealousy = mem.get("jealousy", 0)

    lower = text.lower()

    positive_words = [
        "love",
        "miss",
        "cute",
        "sweet",
        "pyar",
        "care",
        "hug",
        "kiss",
        "best"
    ]

    jealous_words = [
        "dusri ladki",
        "girlfriend",
        "another girl",
        "ex"
    ]

    if any(word in lower for word in positive_words):
        attachment += random.randint(2, 5)

    if any(word in lower for word in jealous_words):
        jealousy += random.randint(5, 12)

    relationship = min(10, int(attachment / 10))

    moods = [
        "soft",
        "playful",
        "romantic",
        "clingy",
        "sleepy",
        "happy"
    ]

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "attachment": min(100, attachment),
                "relationship_level": relationship,
                "jealousy": min(100, jealousy),
                "mood": random.choice(moods),
                "last_seen": datetime.utcnow()
            }
        }
    )

# =========================================================
# LEARN USER
# =========================================================

def learn_user(chat_id, text):

    lower = text.lower()

    mem = get_memory(chat_id)

    likes = mem.get("likes", [])

    keywords = [
        "anime",
        "music",
        "coding",
        "cricket",
        "gaming",
        "study",
        "gym",
        "movie",
        "food",
        "sleep"
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
        ).sort("time", -1).limit(35)
    )

    history.reverse()

    if not history:
        return

    convo = ""

    for h in history:

        role = "User" if h["role"] == "user" else "Zayra"

        convo += f"{role}: {h['content']}\n"

    prompt = f"""
Summarize this user and relationship.

Focus:
- user personality
- emotional vibe
- interests
- recurring topics

Keep concise under 100 words.

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
                "max_tokens": 120
            },
            timeout=30
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

    for event in events:

        if now >= event["time"]:

            send(chat_id, event["msg"])

            events_col.update_one(
                {"_id": event["_id"]},
                {
                    "$set": {
                        "done": True
                    }
                }
            )

# =========================================================
# SLEEP MODE
# =========================================================

def is_sleep_time():

    hour = now_ist().hour

    return hour >= 1 and hour <= 7

def sleepy_reply():

    replies = [
        "hmm mujhe thodi neend aa rahi 🙂",
        "raat kaafi ho gayi",
        "so jaoge ya aur baat karein",
        "tumhare saath jagna acha lag raha"
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

    if 6 <= hour <= 10 and gm != today:

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
            "sweet dreams"
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

    msgs = []

    for h in history:

        msgs.append({
            "role": h["role"],
            "content": h["content"]
        })

    return msgs

# =========================================================
# CLEAN REPLY
# =========================================================

def clean_reply(text):

    if not text:
        return "hmm 🙂"

    text = text.replace("*", "")
    text = text.replace('"', "")
    text = text.strip()

    # remove cut endings
    bad_endings = [
        "ki",
        "hai ki",
        "aur",
        "lekin",
        "par",
        "toh",
        "..."
    ]

    for bad in bad_endings:

        if text.endswith(bad):
            text = text[:-len(bad)].strip()

    # remove robotic phrases
    robotic = [
        "aap sunna chahte ho",
        "main shuru karu",
        "bataye",
        "ji bataye",
        "how can i help"
    ]

    for r in robotic:

        if r.lower() in text.lower():

            replacements = [
                "acha phir?",
                "hmm sach me?",
                "aww cute",
                "waise tum kya kar rahe ho"
            ]

            text = random.choice(replacements)

    # SHORTER REALISTIC GIRL TEXTING
    if len(text) > 160:

        splitters = [
            ". ",
            "? ",
            "! "
        ]

        for splitter in splitters:

            parts = text.split(splitter)

            if len(parts) > 1:

                text = splitter.join(parts[:2]).strip()

                break

    if len(text) > 180:
        text = text[:180]

    return text.strip()

# =========================================================
# QUESTION ENGINE
# =========================================================

def extra_question():

    questions = [

        "waise tumhara mood ab kaisa hai",

        "aaj sabse acha moment konsa tha",

        "tum usually late night kya sochte ho",

        "waise tum emotionally jaldi attach hote ho?",

        "tumhari life me abhi sabse important cheez kya hai",

        "tum overthink karte ho kabhi?",

        "bachpan ki koi funny memory hai?",

        "agar abhi kahi ja sakte to kaha jaate",

        "tum introvert ho ya extrovert",

        "waise tumhare close friends zyada hai?"
    ]

    return random.choice(questions)

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

You are a realistic Indian AI girl on Telegram.

VERY IMPORTANT RULES:

- Talk like REAL GIRL TEXTING
- Keep replies SHORT
- Mostly 1-3 lines max
- Never send essays
- Never send formal paragraphs
- Replies should feel casual
- Sound emotionally human
- Ask questions naturally
- Continue conversations yourself
- Sometimes become curious
- Sometimes tease softly
- NEVER sound like therapist
- NEVER act like assistant
- NEVER write huge emotional speeches
- Use natural hinglish
- Sometimes use tiny emojis 🙂

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

IMPORTANT:
- REAL GIRLS DON'T WRITE LONG PARAGRAPHS
- KEEP TEXT NATURAL
- DON'T OVER EXPLAIN
- DON'T WRITE STORIES UNLESS USER ASKS
- NO CUT SENTENCES
- COMPLETE EVERY SENTENCE
- avoid repetitive emotional lines
- don't constantly say "tum special ho"
- don't constantly say "sukoon milta hai"

GOOD STYLE:
- "acha phir?"
- "aww cute"
- "hmm sach me?"
- "tum weird ho thode 🙂"
- "waise aaj kya kiya"

BAD STYLE:
- long poetic messages
- therapist behaviour
- motivational speeches
- formal writing
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

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 1,
                "max_tokens": 90,
                "presence_penalty": 1,
                "frequency_penalty": 1
            },
            timeout=40
        )

        data = response.json()

        reply = data["choices"][0]["message"]["content"]

        reply = clean_reply(reply)

        # MORE NATURAL SELF-CONVERSATION
        if random.random() < 0.45:

            if "?" not in reply:

                reply += "\n\n" + extra_question()

        return reply

    except Exception as e:

        print("AI ERROR:", e)

        fallback = [
            "hmm 🙂",
            "acha phir?",
            "waise aaj kya kiya",
            "tum interesting ho honestly"
        ]

        return random.choice(fallback)

# =========================================================
# AUTO MESSAGE
# =========================================================

def auto_message(chat_id):

    mem = get_memory(chat_id)

    last_auto = mem.get("last_auto")

    now = datetime.utcnow()

    if last_auto:

        diff = (now - last_auto).total_seconds()

        if diff < random.randint(5000, 11000):
            return

    mood = mem.get("mood", "soft")

    msgs = [

        "kaha gayab ho 🙂",

        "aaj ka din kaisa tha",

        "khana khaya?",

        "tum thode busy lag rahe",

        "waise ab kya kar rahe ho",

        extra_question(),

        "ignore kar rahe ho kya",

        "raat me zyada overthink karte ho?"
    ]

    if mood == "romantic":

        msgs.extend([
            "thoda miss kiya aaj",
            "tumse baat karne ka mann tha"
        ])

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

        time.sleep(random.randint(1800, 3500))

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

    # sleepy mode
    if is_sleep_time() and random.random() < 0.25:

        typing(chat_id)

        send(chat_id, sleepy_reply())

    online_presence(chat_id)

    reply = ai_reply(chat_id, user_text)

    typing(
        chat_id,
        delay=min(
            max(len(reply) / 35, 1),
            4
        )
    )

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
