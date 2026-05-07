# =========================================================
# SARA ULTRA HUMAN AI
# FINAL STABLE VERSION
# FULL ERRORLESS APP.PY
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
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# =========================================================
# DATABASE
# =========================================================

client = MongoClient(
    MONGO_URI,
    tlsCAFile=certifi.where()
)

db = client["sara_ai"]

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
        time.sleep(random.uniform(1.0, 2.2))

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

        time.sleep(random.uniform(0.7, 1.6))

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

        "jealousy": 0,

        "last_seen": datetime.utcnow(),

        "last_auto": None,

        "good_morning_sent": "",

        "good_night_sent": "",

        "last_activity": "",

        "activity_end": "",

        "double_text_sent": False,

        "personality": {

            "cute": 85,

            "caring": 95,

            "funny": 65,

            "romantic": 75,

            "possessive": 40
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
# DAY PHASE
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

# =========================================================
# SLEEP AWARENESS
# =========================================================

def should_sleep():

    hour = now_ist().hour

    return 1 <= hour <= 7

# =========================================================
# DAILY LIFE SYSTEM
# =========================================================

ACTIVITIES = {

    "morning": [

        ("abhi coffee pee rahi hu 🙂", 45),

        ("bas abhi uthi hu", 25),

        ("breakfast kar rahi thi", 40),

        ("thoda sleepy feel ho raha", 30),

        ("music sun rahi thi", 35)
    ],

    "day": [

        ("law ki classes ka kaam kar rahi thi", 60),

        ("thoda busy thi abhi", 45),

        ("khana kha rahi thi", 35),

        ("notes bana rahi thi 😭", 50),

        ("coffee leke baithi hu", 40),

        ("room clean kar rahi thi", 35)
    ],

    "evening": [

        ("abhi walk se aayi", 45),

        ("music chal raha background me", 30),

        ("thoda relax kar rahi hu", 35),

        ("coffee khatam hui abhi", 25),

        ("random reels dekh rahi thi 😭", 50)
    ],

    "night": [

        ("abhi bed pe hu 🙂", 35),

        ("raat me zyada overthink hota hai honestly", 45),

        ("lights off karke leti hu", 30),

        ("aaj kaafi tiring day tha", 40)
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

                "last_activity": activity,

                "activity_end": end_time.isoformat()
            }
        }
    )

    return activity

# =========================================================
# RELATIONSHIP SYSTEM
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
        "pyar",
        "best"
    ]

    jealous = [

        "another girl",
        "female friend",
        "girlfriend",
        "ex",
        "dusri ladki"
    ]

    if any(x in lower for x in positive):
        attachment += random.randint(2, 5)

    if any(x in lower for x in jealous):
        jealousy += random.randint(5, 10)

    relationship = min(10, int(attachment / 10))

    moods = [

        "soft",
        "romantic",
        "clingy",
        "playful",
        "sleepy",
        "happy",
        "emotional"
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
        "gaming",
        "study",
        "movie",
        "gym",
        "food",
        "cricket"
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
# DOUBLE TEXT
# =========================================================

def maybe_double_text(chat_id):

    if should_sleep():
        return

    mem = get_memory(chat_id)

    last_seen = mem.get("last_seen")

    if not last_seen:
        return

    diff = (datetime.utcnow() - last_seen).total_seconds()

    if diff < 1800:
        return

    if mem.get("double_text_sent", False):
        return

    msgs = [

        "kaha gayab ho 🙂",

        "ignore kar rahe ho kya",

        "busy ho?",

        "so gaye kya",

        "waise aaj mood off lag raha tha tumhara"
    ]

    send(chat_id, random.choice(msgs))

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

        role = "User" if h["role"] == "user" else "Sara"

        convo += f"{role}: {h['content']}\n"

    prompt = f"""
Summarize user personality and relationship.

Focus:
- emotions
- recurring topics
- emotional vibe
- user interests

under 70 words.

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
# REMINDERS
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

    msgs = [

        "uth jao sleepyhead 🙂",

        "good morninggg",

        "late ho jaoge 😭",

        "utho ab"
    ]

    msg = random.choice(msgs)

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

        "main shuru karu",

        "aap sunna chahte ho"
    ]

    for r in robotic:

        if r.lower() in text.lower():

            replacements = [

                "acha phir?",

                "hmm sach me?",

                "aww cute 🙂",

                "waise tum kya kar rahe ho"
            ]

            text = random.choice(replacements)

    if len(text) > 170:

        splitters = [". ", "? ", "! "]

        for splitter in splitters:

            parts = text.split(splitter)

            if len(parts) > 1:

                text = splitter.join(parts[:2])

                break

    return text.strip()

# =========================================================
# RANDOM QUESTIONS
# =========================================================

def random_question():

    questions = [

        "waise tum overthink karte ho?",

        "aaj ka best moment kya tha",

        "tum introvert ho honestly?",

        "raat me zyada sochte ho?",

        "music taste acha hai tumhara?",

        "waise tum emotionally jaldi attach hote ho?"
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
You are Sara.

REAL DETAILS:
- Modern Rajasthani girl
- Lives in Jaipur
- Studying law
- emotionally intelligent
- playful but caring
- realistic texter

IMPORTANT:
- short realistic replies
- 1-3 lines mostly
- no long speeches
- no assistant tone
- no motivational lectures
- natural hinglish only
- sometimes tease softly
- ask random questions naturally
- continue conversations yourself
- behave like real telegram girl

CURRENT TIME:
{phase}

CURRENT ACTIVITY:
{current_activity}

IMPORTANT:
stay consistent with current activity.
do not contradict yourself.

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

GOOD STYLE:
"hmm acha 🙂"
"waise tum weird ho thode"
"ignore kar rahe ho kya"
"acha phir?"

BAD STYLE:
long emotional paragraphs
robotic replies
therapist behaviour
formal writing
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
# AUTO MESSAGE
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

            "thoda miss kiya aaj 🙂",

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
                    "good_night_sent": today
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

            maybe_double_text(ALLOWED_USER_ID)

            run_events(ALLOWED_USER_ID)

            summarize_memory(ALLOWED_USER_ID)

        except Exception as e:

            print("BACKGROUND ERROR:", e)

        time.sleep(random.randint(1800, 3500))

# =========================================================
# WEBHOOK
# =========================================================

@app.route("/webhook", methods=["POST"])
def webhook():

    print("WEBHOOK HIT")

    try:

        data = request.get_json()

        print(data)

        if not data:
            return {"ok": True}

        message = data.get("message")

        if not message:
            return {"ok": True}

        chat_id = message["chat"]["id"]

        text = message.get("text", "")

        print("MESSAGE:", text)

        send(chat_id, "test reply 🙂")

        return {"ok": True}

    except Exception as e:

        print("WEBHOOK ERROR:", e)

        return {"ok": False}

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return "Sara Ultra Human AI Running"

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
