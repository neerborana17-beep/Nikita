# =========================================================
# ZAYRA ULTRA HUMAN AI
# FULL UPDATED APP.PY
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

    if not text:
        return

    try:

        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=20
        )

    except Exception as e:
        print("SEND ERROR:", e)

def typing(chat_id, delay=None):

    try:

        requests.post(
            f"{TELEGRAM_API}/sendChatAction",
            json={
                "chat_id": chat_id,
                "action": "typing"
            },
            timeout=20
        )

    except:
        pass

    if delay:
        time.sleep(delay)
    else:
        time.sleep(random.uniform(1, 2.2))

# =========================================================
# ONLINE PRESENCE
# =========================================================

def online_presence(chat_id):

    loops = random.randint(1, 3)

    for _ in range(loops):

        try:

            requests.post(
                f"{TELEGRAM_API}/sendChatAction",
                json={
                    "chat_id": chat_id,
                    "action": "typing"
                },
                timeout=20
            )

        except:
            pass

        time.sleep(random.uniform(0.7, 1.8))

# =========================================================
# DEFAULT MEMORY
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

        "busy": False,

        "last_auto": None,

        "last_seen": datetime.utcnow(),

        "good_morning_sent": "",

        "good_night_sent": "",

        "last_activity": "",

        "activity_time": "",

        "activity_end": "",

        "conversation_mode": "normal",

        "ignored_count": 0,

        "daily_state": "",

        "last_topic": "",

        "double_text_sent": False,

        "personality": {

            "cute": 85,

            "caring": 95,

            "funny": 65,

            "romantic": 75,

            "possessive": 45
        }
    }

# =========================================================
# MEMORY
# =========================================================

def get_memory(chat_id):

    mem = memory_col.find_one({"chat_id": chat_id})

    if not mem:

        mem = default_memory(chat_id)

        memory_col.insert_one(mem)

    return mem

# =========================================================
# DAY/NIGHT AWARENESS
# =========================================================

def current_phase():

    hour = now_ist().hour

    if 5 <= hour < 11:
        return "morning"

    elif 11 <= hour < 17:
        return "day"

    elif 17 <= hour < 22:
        return "evening"

    return "night"

def should_sleep():

    hour = now_ist().hour

    return 1 <= hour <= 7

# =========================================================
# REALISTIC DAILY LIFE ENGINE
# =========================================================

ACTIVITIES = {

    "morning": [

        ("abhi coffee pee rahi hu 🙂", 40),

        ("bas abhi uthi hu", 20),

        ("breakfast kar rahi thi", 35),

        ("thoda sleepy feel ho raha", 25),

        ("music sun rahi thi", 30)
    ],

    "day": [

        ("thoda busy thi abhi", 60),

        ("khana kha rahi thi", 40),

        ("youtube dekh rahi thi", 30),

        ("coding jaisa kuch try kar rahi thi 😭", 45),

        ("coffee leke baithi hu", 35),

        ("abhi room clean kar rahi thi", 40)
    ],

    "evening": [

        ("abhi walk se aayi", 50),

        ("music chal raha background me", 35),

        ("thoda relax kar rahi hu", 40),

        ("coffee khatam hui abhi", 30),

        ("bas random reels dekh rahi thi", 50)
    ],

    "night": [

        ("raat me zyada overthink hota hai honestly", 50),

        ("abhi bed pe hu 🙂", 40),

        ("sleepy feel ho raha", 45),

        ("lights off karke leti hu", 35),

        ("aaj kaafi tiring day tha", 60)
    ]
}

# =========================================================
# ACTIVITY ENGINE
# =========================================================

def set_activity(chat_id):

    mem = get_memory(chat_id)

    current = mem.get("last_activity", "")

    activity_end = mem.get("activity_end", "")

    now = datetime.utcnow()

    if activity_end:

        try:

            end = datetime.fromisoformat(activity_end)

            if now < end:
                return current

        except:
            pass

    phase = current_phase()

    activity, mins = random.choice(ACTIVITIES[phase])

    end_time = now + timedelta(minutes=mins)

    memory_col.update_one(
    {"chat_id": chat_id},
    {
        "$set": {

            "last_seen": datetime.utcnow(),

            "double_text_sent": False
        }
    }
    )

    return activity

# =========================================================
# RELATIONSHIP ENGINE
# =========================================================

def update_relationship(chat_id, text):

    mem = get_memory(chat_id)

    attachment = mem.get("attachment", 20)

    jealousy = mem.get("jealousy", 0)

    lower = text.lower()

    positive = [

        "love",
        "miss",
        "cute",
        "sweet",
        "care",
        "hug",
        "best",
        "pyar"
    ]

    jealous = [

        "another girl",
        "girlfriend",
        "dusri ladki",
        "female friend",
        "ex"
    ]

    if any(x in lower for x in positive):
        attachment += random.randint(2, 5)

    if any(x in lower for x in jealous):
        jealousy += random.randint(5, 10)

    relationship = min(10, int(attachment / 10))

    current_mood = get_persistent_mood(chat_id)

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
# PERSISTENT MOODS
# =========================================================

MOODS = [

    ("soft", 30),

    ("romantic", 25),

    ("clingy", 20),

    ("playful", 20),

    ("sleepy", 15),

    ("emotional", 20),

    ("happy", 30)
]

def get_persistent_mood(chat_id):

    mem = get_memory(chat_id)

    current = mem.get("mood", "soft")

    if random.random() < 0.7:
        return current

    mood = random.choice(MOODS)[0]

    return mood

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
        "gaming",
        "cricket",
        "gym",
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
# DOUBLE TEXT SYSTEM
# =========================================================

def maybe_double_text(chat_id):

    mem = get_memory(chat_id)

    last_seen = mem.get("last_seen")

    if not last_seen:
        return

    diff = (datetime.utcnow() - last_seen).total_seconds()

    if diff < 1800:
        return

    if mem.get("double_text_sent", False):
        return

    if should_sleep():
        return

    texts = [

        "kaha gayab ho 🙂",

        "ignore kar rahe ho kya",

        "so gaye kya",

        "busy ho?",

        "waise aaj mood off lag raha tha tumhara"
    ]

    send(chat_id, random.choice(texts))

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "double_text_sent": True
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
        ).sort("time", -1).limit(30)
    )

    history.reverse()

    if not history:
        return

    convo = ""

    for h in history:

        role = "User" if h["role"] == "user" else "Zayra"

        convo += f"{role}: {h['content']}\n"

    prompt = f"""
Summarize relationship memory.

Focus:
- emotions
- recurring topics
- user personality
- important memories

under 80 words.

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
                "max_tokens": 100
            },
            timeout=30
        )

        summary = r.json()["choices"][0]["message"]["content"]

        summary_col.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "summary": summary
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

    lower = text.lower()

    match = re.search(r'(\d{1,2}) ?baje', lower)

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

    wakeup_msgs = [

        "uth jao sleepyhead 🙂",

        "good morninggg",

        "late ho jaoge 😭",

        "utho ab"
    ]

    msg = random.choice(wakeup_msgs)

    if "yaad" in lower:
        msg = "aapne reminder lagaya tha 🙂"

    events_col.insert_one({

        "chat_id": chat_id,

        "time": remind_time,

        "done": False,

        "msg": msg
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
# CLEAN REPLY
# =========================================================

def clean_reply(text):

    if not text:
        return "hmm 🙂"

    text = text.replace("*", "")

    text = text.replace('"', "")

    text = text.strip()

    robotic = [

        "how can i help",

        "bataye",

        "aap sunna chahte ho",

        "main shuru karu"
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

    if len(text) > 180:

        splitters = [". ", "? ", "! "]

        for splitter in splitters:

            parts = text.split(splitter)

            if len(parts) > 1:

                text = splitter.join(parts[:2])

                break

    return text.strip()

# =========================================================
# QUESTION ENGINE
# =========================================================

def random_question():

    questions = [

        "waise tum overthink karte ho?",

        "aaj ka best moment kya tha",

        "tum introvert ho kya honestly",

        "raat me zyada sochte ho?",

        "waise tum emotionally jaldi attach hote ho?",

        "tumhari comfort cheez kya hai?",

        "music taste acha hai tumhara?"
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

    current_activity = set_activity(chat_id)

    summary_doc = summary_col.find_one({"chat_id": chat_id})

    summary = ""

    if summary_doc:
        summary = summary_doc.get("summary", "")

    personality = mem.get("personality", {})

    phase = current_phase()

    system_prompt = f"""
You are Zayra.

You are a REALISTIC Indian AI girl texting naturally.

IMPORTANT:
- VERY SHORT replies
- 1-3 lines max
- no long paragraphs
- casual texting only
- no assistant behaviour
- no motivational speeches
- no formal writing
- no robotic phrases

CURRENT TIME:
{phase}

CURRENT ACTIVITY:
{current_activity}

IMPORTANT:
Stay consistent with current activity.
Do NOT contradict yourself.

Example:
If currently drinking coffee,
don't later say "i will make coffee".

PERSONALITY:
cute: {personality.get('cute')}
caring: {personality.get('caring')}
funny: {personality.get('funny')}
romantic: {personality.get('romantic')}
possessive: {personality.get('possessive')}

RELATIONSHIP:
level: {relationship}/10
attachment: {attachment}/100
jealousy: {jealousy}/100
mood: {mood}

USER LIKES:
{likes}

MEMORY:
{summary}

IMPORTANT HUMAN RULES:
- sleepy at night
- energetic in daytime
- ask random questions naturally
- sometimes tease softly
- sometimes emotionally curious
- continue conversations yourself
- use tiny texting mistakes sometimes
- use emojis rarely 🙂

GOOD STYLE:
"hmm acha 🙂"
"waise tum weird ho thode"
"acha phir?"
"ignore kar rahe ho kya"

BAD STYLE:
long speeches
therapist tone
formal grammar
robotic replies
"""

    history = list(
        history_col.find(
            {"chat_id": chat_id}
        ).sort("time", -1).limit(15)
    )

    history.reverse()

    messages = [

        {
            "role": "system",
            "content": system_prompt
        }
    ]

    for h in history:

        messages.append({
            "role": h["role"],
            "content": h["content"]
        })

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

        # natural curiosity

        if random.random() < 0.40:

            if "?" not in reply:

                reply += "\n\n" + random_question()

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
# AUTO MESSAGE ENGINE
# =========================================================

def auto_message(chat_id):

    if should_sleep():
        return

    mem = get_memory(chat_id)

    last_auto = mem.get("last_auto")

    now = datetime.utcnow()

    if last_auto:

        diff = (now - last_auto).total_seconds()

        if diff < random.randint(5000, 12000):
            return

    mood = mem.get("mood", "soft")

    activity = set_activity(chat_id)

    msgs = [

        activity,

        "kaha gayab ho 🙂",

        "waise aaj kya kar rahe ho",

        "khana khaya?",

        random_question(),

        "ignore kar rahe ho kya"
    ]

    if mood == "romantic":

        msgs.extend([

            "thoda miss kiya aaj",

            "tumse baat karne ka mann tha 🙂"
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

            "sleep schedule fix karo 😭"
        ]

        send(chat_id, random.choice(msgs))

        memory_col.update_one(
    {"chat_id": chat_id},
    {
        "$set": {

            "last_seen": datetime.utcnow(),

            "double_text_sent": False
        }
    }
        )
