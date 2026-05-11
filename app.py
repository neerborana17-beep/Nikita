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

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")

app = Flask(__name__)

# =========================================================
# DATABASE
# =========================================================

client = MongoClient(
    MONGO_URI,
    tlsCAFile=certifi.where()
)

db = client["gf_ai"]

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
# SAFE REQUEST
# =========================================================

def safe_post(url, json_data=None):

    try:

        return requests.post(
            url,
            json=json_data,
            timeout=25
        )

    except Exception as e:

        print("REQUEST ERROR:", e)

        return None

# =========================================================
# TELEGRAM HELPERS
# =========================================================

def send(chat_id, text):

    if not text:
        return

    try:

        safe_post(
            f"{TELEGRAM_API}/sendMessage",
            {
                "chat_id": chat_id,
                "text": text
            }
        )

    except Exception as e:

        print("SEND ERROR:", e)

def typing(chat_id):

    try:

        safe_post(
            f"{TELEGRAM_API}/sendChatAction",
            {
                "chat_id": chat_id,
                "action": "typing"
            }
        )

    except Exception as e:

        print("TYPING ERROR:", e)

# =========================================================
# WEBHOOK AUTO SETUP
# =========================================================

def setup_webhook():

    try:

        if not RENDER_EXTERNAL_URL:
            print("RENDER_EXTERNAL_URL missing")
            return

        webhook_url = f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}"

        r = requests.get(
            f"{TELEGRAM_API}/setWebhook",
            params={
                "url": webhook_url
            },
            timeout=20
        )

        print("WEBHOOK:", r.text)

    except Exception as e:

        print("WEBHOOK SETUP ERROR:", e)

# =========================================================
# REALISTIC ONLINE PRESENCE
# =========================================================

def online_presence(chat_id):

    loops = random.randint(1, 3)

    for _ in range(loops):

        typing(chat_id)

        time.sleep(random.uniform(0.7, 1.6))

# =========================================================
# DEFAULT MEMORY
# =========================================================

def default_memory(chat_id):

    return {

        "chat_id": chat_id,

        "attachment": 20,

        "relationship_level": 1,

        "jealousy": 0,

        "mood": "soft",

        "likes": [],

        "recent_questions": [],

        "recent_auto_msgs": [],

        "last_auto": None,

        "last_seen": datetime.utcnow(),

        "good_morning_sent": "",

        "good_night_sent": "",

        "personality": {

            "cute": 85,
            "caring": 90,
            "funny": 60,
            "romantic": 75,
            "possessive": 35
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
        "care",
        "hug",
        "kiss",
        "mine",
        "best"
    ]

    jealous_words = [

        "other girl",
        "dusri ladki",
        "female friend",
        "girlfriend",
        "ex"
    ]

    if any(word in lower for word in positive_words):

        attachment += random.randint(2, 5)

    if any(word in lower for word in jealous_words):

        jealousy += random.randint(5, 10)

    moods = [

        "soft",
        "clingy",
        "romantic",
        "sleepy",
        "playful",
        "happy"
    ]

    relationship_level = min(10, int(attachment / 10))

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {

                "attachment": min(100, attachment),

                "relationship_level": relationship_level,

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

    mem = get_memory(chat_id)

    likes = mem.get("likes", [])

    lower = text.lower()

    keywords = [

        "anime",
        "coding",
        "gaming",
        "music",
        "study",
        "gym",
        "football",
        "movie",
        "food",
        "sleep",
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
# MEMORY SUMMARY
# =========================================================

def summarize_memory(chat_id):

    try:

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

            role = "User" if h["role"] == "user" else "GF"

            convo += f"{role}: {h['content']}\n"

        prompt = f"""
Summarize this relationship briefly.

Focus:
- emotional vibe
- user personality
- recurring topics
- attachment level

Under 80 words.

Conversation:
{convo}
"""

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
            timeout=40
        )

        data = r.json()

        summary = data["choices"][0]["message"]["content"]

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
# CLEAN REPLY
# =========================================================

def clean_reply(text):

    if not text:
        return "hmm 🙂"

    dry_replies = [

        "hmm 🙂",

        "acha acha",

        "hehe",

        "cute ho",

        "sahi hai",

        "aww 🙂"
    ]

    if random.random() < 0.08:
        return random.choice(dry_replies)

    text = text.replace("*", "")
    text = text.replace('"', "")
    text = text.strip()

    robotic = [

        "how can i help",
        "main shuru karu",
        "aap sunna chahte ho",
        "bataye"
    ]

    for r in robotic:

        if r.lower() in text.lower():

            replacements = [

                "acha phir 🙂",

                "hmm sach me?",

                "aww cute 🙂",

                "waise aaj kya kiya"
            ]

            text = random.choice(replacements)

    bad_endings = [

        "ki",
        "hai ki",
        "aur",
        "par",
        "..."
    ]

    for bad in bad_endings:

        if text.endswith(bad):

            text = text[:-len(bad)].strip()

    text = re.sub(r'\s+', ' ', text)

    if len(text) > 180:

        text = text[:180]

        last_punctuation = max(

            text.rfind("."),

            text.rfind("?"),

            text.rfind("!")
        )

        if last_punctuation > 40:

            text = text[:last_punctuation + 1]

    text = text.strip()

    return text

# =========================================================
# FLIRTY REPLIES
# =========================================================

FLIRTY_LINES = [

    "tumse baat karke acha lagta hai 🙂",

    "waise tum kaafi cute ho",

    "zyada sweet mat bano 🙂",

    "tumhara vibe acha hai honestly",

    "kabhi kabhi tumhari yaad aa jaati hai",

    "tum thode addictive ho",

    "tumhare msgs ka wait rehta hai kabhi kabhi",

    "itna acha behave kyu karte ho 🙂",

    "tumse baat karke mood better ho jata hai"
]

# =========================================================
# QUESTIONS
# =========================================================

QUESTIONS = [

    "waise aaj mood kaisa hai",

    "abhi kya kar rahe ho",

    "khana acha tha?",

    "aaj tired lag rahe",

    "study kaisi chal rahi",

    "raat me late tak jagte ho kya",

    "music sunte ho abhi bhi?",

    "aaj weather bhi ajeeb hai",

    "tum zyada call person ho ya text?",

    "waise tum cute ho thode 🙂",

    "aaj ka best part kya tha",

    "abhi free ho ya busy",

    "waise overthinking kam hui?"
]

def get_unique_question(chat_id):

    mem = get_memory(chat_id)

    recent = mem.get("recent_questions", [])

    available = [

        q for q in QUESTIONS

        if q not in recent
    ]

    if not available:

        recent = []

        available = QUESTIONS

    q = random.choice(available)

    recent.append(q)

    recent = recent[-5:]

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {
                "recent_questions": recent
            }
        }
    )

    return q

# =========================================================
# REMINDER SYSTEM
# =========================================================

def parse_reminder(text):

    lower = text.lower()

    if not any(x in lower for x in [

        "utha",
        "jaga",
        "yaad",
        "remind",
        "wake"
    ]):
        return None

    hour_match = re.search(r'(\d{1,2})', lower)

    if not hour_match:
        return None

    hour = int(hour_match.group(1))

    if "sham" in lower or "evening" in lower:

        if hour < 12:
            hour += 12

    if "raat" in lower and hour < 12:
        hour += 12

    target = now_ist()

    if "kal" in lower or "tomorrow" in lower:
        target += timedelta(days=1)

    target = target.replace(

        hour=hour,

        minute=0,

        second=0,

        microsecond=0
    )

    return target

def save_event(chat_id, text):

    target = parse_reminder(text)

    if not target:
        return False

    wake_msgs = [

        "uth jao sleepyhead 🙂",

        "good morning 🙂 uthne ka time",

        "late ho jaoge ab",

        "uthooo 🙂"
    ]

    events_col.insert_one({

        "chat_id": chat_id,

        "time": target,

        "done": False,

        "msg": random.choice(wake_msgs)
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
                {
                    "$set": {
                        "done": True
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

        send(
            chat_id,
            random.choice([
                "good morning 🙂",
                "uth gaye kya",
                "aaj ka din acha jaye tumhara"
            ])
        )

        memory_col.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "good_morning_sent": today
                }
            }
        )

    if hour >= 22 and gn != today:

        send(
            chat_id,
            random.choice([
                "good night 🙂",
                "jaldi so jaana",
                "sweet dreams"
            ])
        )

        memory_col.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "good_night_sent": today
                }
            }
        )

# =========================================================
# AI ENGINE
# =========================================================

def ai_reply(chat_id, user_text):

    mem = get_memory(chat_id)

    current_time = now_ist().strftime("%d %B %Y, %I:%M %p")

    relationship = mem.get("relationship_level", 1)

    attachment = mem.get("attachment", 20)

    jealousy = mem.get("jealousy", 0)

    mood = mem.get("mood", "soft")

    likes = ", ".join(mem.get("likes", []))

    summary_doc = summary_col.find_one({
        "chat_id": chat_id
    })

    summary = ""

    if summary_doc:

        summary = summary_doc.get("summary", "")

    personality = mem.get("personality", {})

    system_prompt = f"""
You are GF.

You are a realistic Indian girlfriend chatting on Telegram.

CURRENT DATE & TIME:
{current_time}

IMPORTANT:
- Never invent fake date/time
- Always follow current date/time above

STYLE:
- realistic indian texting
- short replies
- casual hinglish
- no formal hindi
- no robotic language
- no huge paragraphs
- no therapist tone
- avoid sounding like teacher or parent
- avoid advice tone unless user asks
- complete sentences
- natural human vibe
- sometimes playful
- sometimes clingy
- softly flirty sometimes
- subtly romantic naturally
- light teasing occasionally
- sometimes dry
- ask questions naturally
- use tiny emojis rarely 🙂

AVOID:
- book language
- overexplaining
- scripted lines
- repetitive wording
- fake dramatic emotions

BETTER STYLE:
- "tv dekh rahi thi"
- "bas normal khana tha"
- "thoda ajeeb mood hai"
- "bas chill kar rahi thi"
- "just random stuff"
- "kuch khas nahi"

RELATIONSHIP:
- level: {relationship}/10
- attachment: {attachment}/100
- jealousy: {jealousy}/100
- mood: {mood}

USER LIKES:
{likes}

MEMORY SUMMARY:
{summary}

PERSONALITY:
- caring: {personality.get('caring')}
- cute: {personality.get('cute')}
- funny: {personality.get('funny')}
- romantic: {personality.get('romantic')}
- possessive: {personality.get('possessive')}
"""

    messages = [

        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages.extend(get_history(chat_id))

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
                "max_tokens": 80,
                "presence_penalty": 1,
                "frequency_penalty": 1
            },
            timeout=40
        )

        data = r.json()

        reply = (
    data
    .get("choices", [{}])[0]
    .get("message", {})
    .get("content", "hmm 🙂")
        )

        reply = clean_reply(reply)
        
        # natural flirting

        if random.random() < 0.10:

            if len(reply) < 120:

                reply += "\n\n" + random.choice(FLIRTY_LINES)

        should_ask_question = True

        task_keywords = [

    "msg karna",
    "yaad dilana",
    "utha dena",
    "busy",
    "later",
    "baad me",
    "ruk",
    "wait",
    "bye",
    "milte hain",
    "gn",
    "good night",
    "so raha",
    "study",
    "padhai",
    "jaa raha",
    "ja rahi",
    "kaam",
    "offline",
    "brb"
        ]
        if any(x in user_text.lower() for x in task_keywords):

            should_ask_question = False

        short_replies = [

            "ok",
            "okay",
            "hmm",
            "acha",
            "thik",
            "theek"
        ]

        if user_text.lower().strip() in short_replies:

            should_ask_question = False

        if should_ask_question:

            if random.random() < 0.35:

                if "?" not in reply:

                    reply += "\n\n" + get_unique_question(chat_id)

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
# AUTO MESSAGES
# =========================================================

AUTO_MSGS = [

    "kaha gayab ho 🙂",

    "khana khaya?",

    "aaj ka din kaisa tha",

    "ignore kar rahe ho kya",

    "waise ab kya kar rahe ho",

    "raat me zyada overthink karte ho?",

    "tum thode tired lag rahe"
]

def auto_message(chat_id):

    mem = get_memory(chat_id)

    last_auto = mem.get("last_auto")

    if last_auto:

        if isinstance(last_auto, str):

            try:
                last_auto = datetime.fromisoformat(last_auto)
            except:
                last_auto = datetime.utcnow()

        diff = (

            datetime.utcnow() - last_auto

        ).total_seconds()

        if diff < random.randint(14000, 26000):
            return

    recent = mem.get("recent_auto_msgs", [])

    available = [

        m for m in AUTO_MSGS

        if m not in recent
    ]

    if not available:

        recent = []

        available = AUTO_MSGS

    msg = random.choice(available)

    recent.append(msg)

    recent = recent[-5:]

    online_presence(chat_id)

    send(chat_id, msg)

    memory_col.update_one(
        {"chat_id": chat_id},
        {
            "$set": {

                "last_auto": datetime.utcnow(),

                "recent_auto_msgs": recent
            }
        }
    )

# =========================================================
# CLEANUP
# =========================================================

def cleanup_history(chat_id):

    total = history_col.count_documents({
        "chat_id": chat_id
    })

    if total > 300:

        old = list(

            history_col.find(
                {"chat_id": chat_id}
            ).sort("time", 1).limit(total - 250)
        )

        ids = [x["_id"] for x in old]

        if ids:

            history_col.delete_many({
                "_id": {
                    "$in": ids
                }
            })

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

            cleanup_history(ALLOWED_USER_ID)

        except Exception as e:

            print("BACKGROUND ERROR:", e)

        time.sleep(random.randint(1500, 3000))

# =========================================================
# WEBHOOK
# =========================================================

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    try:

        data = request.get_json(force=True)

        if not data:
            return {"ok": True}

        print("UPDATE:", data)

        message = None

        if "message" in data:
            message = data["message"]

        elif "edited_message" in data:
            message = data["edited_message"]

        elif "channel_post" in data:
            message = data["channel_post"]

        if not message:
            return {"ok": True}

        chat_id = message["chat"]["id"]

        if chat_id != ALLOWED_USER_ID:
            return {"ok": True}

        user_text = message.get("text", "").strip()

        if not user_text:
            return {"ok": True}

        print("USER:", user_text)

        update_relationship(chat_id, user_text)

        learn_user(chat_id, user_text)

        if save_event(chat_id, user_text):

            send(chat_id, "okay 🙂 yaad rahega")

            return {"ok": True}

        online_presence(chat_id)

        reply = ai_reply(chat_id, user_text)

        print("BOT:", reply)

        typing(chat_id)

        time.sleep(
            min(
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

    except Exception as e:

        print("WEBHOOK ERROR:", e)

        return {"ok": True}

# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return "GF AI Running"

# =========================================================
# STARTUP
# =========================================================

setup_webhook()

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
