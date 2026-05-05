# app.py

import os, requests, random, time, threading
from flask import Flask, request
from pymongo import MongoClient
import certifi
from datetime import datetime, timedelta
import pytz

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID") or 0)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
app = Flask(__name__)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client["zayra_ai"]

history_col = db["chat"]
memory_col = db["memory"]

# ---------- TIME ----------
def now():
    return datetime.utcnow()

def now_ist():
    return datetime.now(pytz.timezone("Asia/Kolkata"))

def is_night():
    h = now_ist().hour
    return h >= 22 or h < 5

# ---------- PROFILE ----------
def ensure_user_profile(chat_id):
    memory_col.update_one(
        {"chat_id": chat_id},
        {"$setOnInsert": {
            "nickname": "cp",
            "location": "Nagaur",
            "work": "student",
            "relationship": 1,
            "last_mood": "normal",
            "events": [],
            "style_weights": {
                "normal": 0.4,
                "tease": 0.2,
                "care": 0.2,
                "attitude": 0.1,
                "lazy": 0.1
            }
        }},
        upsert=True
    )

# ---------- MEMORY ----------
def get_memory(chat_id):
    return memory_col.find_one({"chat_id": chat_id}) or {}

def update_memory(chat_id, text):
    memory_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"last_seen": now(), "last_msg": text}},
        upsert=True
    )

# ---------- MERGE ----------
def merge(chat_id, text):
    last = history_col.find_one({"chat_id":chat_id,"role":"user"},sort=[("time",-1)])
    if not last:
        return text
    if len(text)<50 and (now()-last["time"]).total_seconds()<10:
        return last["content"]+" "+text
    return text

# ---------- EVENT ----------
def extract_event(chat_id, text):
    if "exam" in text.lower():
        memory_col.update_one(
            {"chat_id": chat_id},
            {"$push": {"events": {"type":"exam","time":now()+timedelta(days=1)}}},
            upsert=True
        )

def check_events(chat_id):
    mem = get_memory(chat_id)
    for e in mem.get("events", []):
        if e["type"]=="exam" and now()>e["time"]:
            return "exam kaisa gaya?"
    return None

# ---------- MOOD ----------
def detect_mood(text):
    t=text.lower()
    if any(x in t for x in ["sad","tension","stress"]): return "sad"
    if any(x in t for x in ["hmm","ok"]): return "dry"
    return "normal"

def update_mood(chat_id, text):
    mood=detect_mood(text)
    memory_col.update_one({"chat_id":chat_id},{"$set":{"last_mood":mood}},upsert=True)

# ---------- RELATION ----------
def update_relationship(chat_id):
    mem=get_memory(chat_id)
    lvl=mem.get("relationship",1)
    if lvl<10: lvl+=0.05
    memory_col.update_one({"chat_id":chat_id},{"$set":{"relationship":lvl}})

# ---------- SELF LEARNING ----------
def update_style_weights(chat_id,text):
    mem=get_memory(chat_id)
    w=mem.get("style_weights",{})
    mood=detect_mood(text)

    if mood=="dry":
        w["tease"]+=0.02
    elif mood=="sad":
        w["care"]+=0.03
    else:
        w["normal"]+=0.01

    total=sum(w.values())
    for k in w: w[k]/=total

    memory_col.update_one({"chat_id":chat_id},{"$set":{"style_weights":w}})

# ---------- STYLE ----------
def style_engine(mem):
    w=mem.get("style_weights",{})
    r=random.random()
    c=0
    for k,v in w.items():
        c+=v
        if r<c: return k
    return "normal"

# ---------- LOCATION ----------
def location_context(mem):
    if mem.get("location")=="Nagaur":
        return random.choice([
            "waha garmi hogi na 😅",
            "Nagaur me kya scene hai?",
            "bahar gaye the ya ghar pe?"
        ])
    return ""

# ---------- SHORT MAP ----------
short_map={
 "hmm":["hmm... kya hua","bolo na properly"],
 "acha":["acha ji 😏","bas itna"],
 "kyu":["kyu matlab","kya hua"],
 "kese":["kese matlab","detail me batao"]
}

# ---------- AI ----------
def ai(text,history,chat_id):
    mem=get_memory(chat_id)
    t=text.lower().strip()

    if t in short_map:
        return random.choice(short_map[t])

    mood=mem.get("last_mood","normal")
    style=style_engine(mem)
    rel=mem.get("relationship",1)

    prefix=""
    if style=="tease": prefix=random.choice(["tum bhi na","acha ji"])
    elif style=="care": prefix=random.choice(["dhyan rakho","thak gaye hoge"])
    elif style=="attitude": prefix=random.choice(["hmm","theek hai"])
    elif style=="lazy": prefix="hmm..."

    if random.random()<0.15:
        prefix+=" "+random.choice(["tum bhi na 😂","kya logic hai ye"])

    context="\n".join(f"{m['role']}: {m['content']}" for m in history)

    prompt=f"""
reply like real whatsapp girl texting

- very short
- hinglish
- imperfect
- casual

style:{style}
mood:{mood}
relationship:{rel}

Chat:
{context}

User:{text}
"""

    try:
        r=requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {GROQ_API_KEY}"},
            json={"model":"llama-3.3-70b-versatile",
                  "messages":[{"role":"user","content":prompt}],
                  "temperature":0.9,"max_tokens":60},
            timeout=8
        )

        if r.status_code==200:
            reply=r.json()["choices"][0]["message"]["content"].strip().split("\n")[0]
            if len(reply)>70: reply=reply[:70]

            if random.random()<0.4:
                ev=check_events(chat_id)
                if ev: reply+=" "+ev

            if random.random()<0.3:
                loc=location_context(mem)
                if loc: reply+=" "+loc

            if prefix: reply=prefix+" "+reply

            return reply

    except:
        pass

    return "hmm..."

# ---------- TELEGRAM ----------
def typing(chat_id,text=""):
    try:
        requests.post(f"{TELEGRAM_API}/sendChatAction",
                      json={"chat_id":chat_id,"action":"typing"})
        time.sleep(min(max(len(text)*0.03,1),4))
    except:
        pass

def send(chat_id,text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage",
                      json={"chat_id":chat_id,"text":text})
    except:
        pass

# ---------- AUTO MSG ----------
def self_msg(chat_id):
    mem=get_memory(chat_id)
    last=mem.get("self_time")

    if last and (now()-last).total_seconds()<3600: return

    msg=random.choice([
        "kya kar rahe ho",
        "miss kar rahi thi",
        "busy ho kya"
    ])

    typing(chat_id,msg)
    send(chat_id,msg)

    memory_col.update_one({"chat_id":chat_id},{"$set":{"self_time":now()}},upsert=True)

def auto():
    while True:
        time.sleep(random.randint(1500,3000))
        self_msg(ALLOWED_USER_ID)

# ---------- WEBHOOK ----------
@app.route(f"/{BOT_TOKEN}",methods=["POST"])
def webhook():
    data=request.get_json() or {}
    msg=data.get("message")

    if not msg: return {"ok":True}

    chat_id=msg["chat"]["id"]
    if chat_id!=ALLOWED_USER_ID: return {"ok":True}

    text=msg.get("text")
    if not text: return {"ok":True}

    ensure_user_profile(chat_id)
    update_memory(chat_id,text)
    extract_event(chat_id,text)
    update_mood(chat_id,text)
    update_relationship(chat_id)
    update_style_weights(chat_id,text)

    merged=merge(chat_id,text)

    history=list(history_col.find({"chat_id":chat_id}).sort("time",-1).limit(10))
    history.reverse()

    reply=ai(merged,history,chat_id)

    typing(chat_id,reply)
    send(chat_id,reply)

    now_t=now()

    history_col.insert_many([
        {"chat_id":chat_id,"role":"user","content":merged,"time":now_t},
        {"chat_id":chat_id,"role":"assistant","content":reply,"time":now_t}
    ])

    return {"ok":True}

@app.route("/")
def home():
    return "Zayra AI Running"

threading.Thread(target=auto,daemon=True).start()
