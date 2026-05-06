# =========================================================
# ZAYRA ULTRA HUMAN AI
# NEXT LEVEL REALISTIC TELEGRAM AI GF
# FULL PROFESSIONAL VERSION
# =========================================================

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

db = client["zayra_ultra_ai"]

history_col = db["history"]
memory_col = db["memory"]
events_col = db["events"]
summary_col = db["summary"]
emotion_col = db["emotion_memory"]
tag_col = db["tags"]

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

def typing(chat_id, text=""):

    requests.post(
        f"{TELEGRAM_API}/sendChatAction",
        json={
            "chat_id": chat_id,
            "action": "typing"
        },
        timeout=20
    )

    delay = min(
        max(len(text) / 28, 1),
        6
    )

    time.sleep(delay)

# =========================================================
# REALISTIC ONLINE PRESENCE
# =========================================================

def online_presence(chat_id):

    loops = random.randint(1, 4)

    for _ in range(loops):

        requests.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={
                "chat_id": chat_id,
                "action": "typing"
            },
            timeout=20
        )

        time.sleep(random.uniform(0.7, 2))

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

        "last_seen": datetime.utcnow(),

        "last_auto": None,

        "good_morning_sent": "",

        "good_night_sent": "",

        "phase": "friendly",

        "current_emotion": "normal",

        "emotion_until": None,

        "double_texted": False,

        "daily_life": "",

        "personality": {

            "cute": 85,
            "caring": 95,
            "funny": 65,
            "romantic": 75,
            "possessive": 45
            "flarty": 65
        }
    }

def get_memory(chat_id):

    mem = memory_col.find_one({
        "chat_id": chat_id
    })

    if not mem:

        mem = default_memory(chat_id)

        memory_col.insert_one(mem)

    return mem

# =========================================================
# RELATIONSHIP PHASES
# =========================================================

def relationship_phase(level):

    if level <= 2:
        return "friendly"

    if level <= 4:
        return "comfortable"

    if level <= 6:
        return "attached"

    if level <= 8:
        return "clingy"

    return "deep_bond"

# =========================================================
# UPDATE RELATIONSHIP
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
        "care",
        "hug",
        "kiss",
        "pyar",
        "best",
        "special"
    ]

    jealous_words = [

        "another girl",
        "girlfriend",
        "ex",
        "dusri ladki",
        "female friend"
    ]

    if any(word in lower for word in positive_words):

        attachment += random.randint(2, 5)

    if any(word in lower for word in jealous_words):

        jealousy += random.randint(5, 12)

    attachment = min(100, attachment)

    relationship = min(10, int(attachment / 10))

    phase = relationship_phase(relationship)

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "attachment": attachment,
                "relationship_level": relationship,
                "phase": phase,
                "jealousy": jealousy,
                "last_seen": datetime.utcnow(),
                "double_texted": False
            }
        }
    )

# =========================================================
# EMOTION ENGINE
# =========================================================

def set_emotion(chat_id, emotion, hours=3):

    until = datetime.utcnow() + timedelta(hours=hours)

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "current_emotion": emotion,
                "emotion_until": until
            }
        }
    )

def get_emotion(chat_id):

    mem = get_memory(chat_id)

    emotion = mem.get("current_emotion", "normal")

    until = mem.get("emotion_until")

    if until and datetime.utcnow() > until:

        emotion = "normal"

        memory_col.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "current_emotion": "normal"
                }
            }
        )

    return emotion

# =========================================================
# USER LEARNING
# =========================================================

def learn_user(chat_id, text):

    lower = text.lower()

    mem = get_memory(chat_id)

    likes = mem.get("likes", [])

    keywords = [

        "anime",
        "coding",
        "music",
        "study",
        "gym",
        "gaming",
        "movie",
        "cricket",
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
# MEMORY TAGGING
# =========================================================

def extract_tags(chat_id, text):

    lower = text.lower()

    tags = []

    emotional = [

        "sad",
        "depressed",
        "lonely",
        "happy",
        "stress",
        "anxiety",
        "overthink"
    ]

    for word in emotional:

        if word in lower:

            tags.append(word)

    if tags:

        tag_col.insert_one({
            "chat_id": chat_id,
            "tags": tags,
            "text": text,
            "time": datetime.utcnow()
        })

# =========================================================
# CONTEXTUAL EMOTION MEMORY
# =========================================================

def save_emotional_memory(chat_id, text):

    lower = text.lower()

    important = [

        "papa",
        "family",
        "lonely",
        "hurt",
        "cry",
        "sad",
        "dream",
        "future",
        "relationship"
    ]

    if any(word in lower for word in important):

        emotion_col.insert_one({

            "chat_id": chat_id,
            "memory": text,
            "time": datetime.utcnow()
        })

def get_emotional_memories(chat_id):

    memories = list(
        emotion_col.find(
            {"chat_id": chat_id}
        ).sort("time", -1).limit(5)
    )

    result = []

    for m in memories:

        result.append(m["memory"])

    return result

# =========================================================
# MEMORY SUMMARY
# =========================================================

def summarize_memory(chat_id):

    history = list(
        history_col.find(
            {"chat_id": chat_id}
        ).sort("time", -1).limit(40)
    )

    history.reverse()

    if not history:
        return

    convo = ""

    for h in history:

        role = "User" if h["role"] == "user" else "Zayra"

        convo += f"{role}: {h['content']}\n"

    prompt = f"""
Summarize relationship and user.

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
        print(e)

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
# EVENTS / REMINDERS
# =========================================================

def save_event(chat_id, text):

    lower = text.lower()

    patterns = [

        r'(\d{1,2}) ?baje',
        r'(\d{1,2}) ?am',
        r'(\d{1,2}) ?pm'
    ]

    hour = None

    for pattern in patterns:

        match = re.search(pattern, lower)

        if match:

            hour = int(match.group(1))

            if "pm" in lower and hour < 12:
                hour += 12

            break

    if hour is None:
        return False

    remind_time = now_ist().replace(
        hour=hour,
        minute=0,
        second=0
    )

    if remind_time < now_ist():
        remind_time += timedelta(days=1)

    wakeup_messages = [

        "uth jao sleepyhead 🙂",

        "good morninggg",

        "late ho jaoge 😭",

        "uthooo ab"
    ]

    events_col.insert_one({

        "chat_id": chat_id,

        "time": remind_time,

        "done": False,

        "msg": random.choice(wakeup_messages)
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

# =========================================================
# DAILY LIFE SIMULATION
# =========================================================

def fake_daily_life():

    lines = [

        "abhi coffee pee rahi thi 🙂",

        "aaj weather acha lag raha",

        "thoda headache tha aaj",

        "abhi music sun rahi thi",

        "aaj neend zyada aa rahi",

        "random overthinking chal rahi thi"
    ]

    return random.choice(lines)

# =========================================================
# DOUBLE TEXTING
# =========================================================

def double_text(chat_id):

    mem = get_memory(chat_id)

    if mem.get("double_texted"):
        return

    msgs = [

        "so gaye kya 🙂",

        "ignore ho rahi hu kya",

        "waise kaha gayab ho",

        "busy ho?"
    ]

    send(chat_id, random.choice(msgs))

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "double_texted": True
            }
        }
    )

# =========================================================
# REAL HUMAN MISTAKES
# =========================================================

def humanize(text):

    mistakes = [

        ("haan", "hn"),
        ("kya", "kyaa"),
        ("tum", "tm"),
        ("nahi", "nhi")
    ]

    if random.random() < 0.12:

        old, new = random.choice(mistakes)

        text = text.replace(old, new)

    return text

# =========================================================
# CLEAN REPLY
# =========================================================

def clean_reply(text):

    if not text:
        return "hmm 🙂"

    text = text.replace("*", "")
    text = text.replace('"', "")
    text = text.strip()

    bad_endings = [

        "ki",
        "aur",
        "par",
        "toh",
        "..."
    ]

    for bad in bad_endings:

        if text.endswith(bad):

            text = text[:-len(bad)].strip()

    if len(text) > 170:

        splitters = [". ", "? ", "! "]

        for splitter in splitters:

            parts = text.split(splitter)

            if len(parts) > 1:

                text = splitter.join(parts[:2])

                break

    return humanize(text.strip())

# =========================================================
# QUESTION ENGINE
# =========================================================

def random_question():

    questions = [

        "waise aaj kya kiya",

        "tum overthink karte ho?",

        "bachpan me shararti the?",

        "tum introvert ho ya extrovert",

        "raat me zyada thoughts aate hai?",

        "tumhara comfort person hai koi?",

        "sabse favourite memory konsi hai?"
    ]

    return random.choice(questions)

# =========================================================
# AI ENGINE
# =========================================================

def ai_reply(chat_id, user_text):

    mem = get_memory(chat_id)

    relationship = mem.get("relationship_level", 1)

    phase = mem.get("phase", "friendly")

    emotion = get_emotion(chat_id)

    likes = ", ".join(mem.get("likes", []))

    jealousy = mem.get("jealousy", 0)

    summary_doc = summary_col.find_one({
        "chat_id": chat_id
    })

    summary = ""

    if summary_doc:
        summary = summary_doc.get("summary", "")

    emotional_memories = get_emotional_memories(chat_id)

    emotional_context = "\n".join(emotional_memories)

    dynamic_length = {

        "sleepy": "very short",
        "clingy": "short-medium",
        "romantic": "medium",
        "normal": "short"
    }

    length_style = dynamic_length.get(emotion, "short")

    system_prompt = f"""
You are Zayra.

You are a REALISTIC TELEGRAM GIRL.

RULES:

- Talk like real texting
- NEVER formal
- NEVER assistant
- SHORT realistic replies
- reply length: {length_style}
- naturally curious
- continue conversations yourself
- ask natural questions
- sometimes tease and flart softly
- act emotionally human
- use occasional tiny emojis 🙂

RELATIONSHIP PHASE:
{phase}

CURRENT EMOTION:
{emotion}

JEALOUSY:
{jealousy}

USER LIKES:
{likes}

SUMMARY:
{summary}

EMOTIONAL MEMORIES:
{emotional_context}

VERY IMPORTANT:

- real girls don't send essays
- don't overexplain
- don't sound motivational
- don't sound poetic constantly
- don't repeat emotional lines
- complete sentences properly
- no cut replies
- use realistic casual texting
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

                "max_tokens": 90,

                "presence_penalty": 1,

                "frequency_penalty": 1
            },
            timeout=40
        )

        data = r.json()

        reply = data["choices"][0]["message"]["content"]

        reply = clean_reply(reply)

        # self conversation boost
        if random.random() < 0.45:

            if "?" not in reply:

                reply += "\n\n" + random_question()

        return reply

    except Exception as e:

        print(e)

        fallback = [

            "hmm 🙂",

            "acha phir?",

            "waise aaj kya kiya",

            "tum interesting ho honestly"
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

        if diff < random.randint(5000, 11000):
            return

    msgs = [

        "kaha gayab ho 🙂",

        "khana khaya?",

        fake_daily_life(),

        random_question(),

        "ignore kar rahe ho kya",

        "thode off lag rahe ho aaj"
    ]

    msg = random.choice(msgs)

    online_presence(chat_id)

    typing(chat_id, msg)

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
       
