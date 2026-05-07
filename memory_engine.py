from pymongo import MongoClient
from datetime import datetime
import os

client = MongoClient(os.getenv("MONGO_URI"))
db = client["ai_gf"]

users = db["users"]
memories = db["memories"]

def get_user(user_id):
    user = users.find_one({"user_id": user_id})

    if not user:
        user = {
            "user_id": user_id,
            "mood": "neutral",
            "relationship_phase": "new",
            "affection": 10,
            "sleeping": False,
            "last_seen": str(datetime.utcnow()),
            "routine": {},
            "personality": {
                "clingy": 30,
                "jealous": 20,
                "romantic": 40
            }
        }

        users.insert_one(user)

    return user

def update_user(user_id, data):
    users.update_one(
        {"user_id": user_id},
        {"$set": data}
    )

def add_memory(user_id, role, text, tags=[]):
    memories.insert_one({
        "user_id": user_id,
        "role": role,
        "text": text,
        "tags": tags,
        "time": datetime.utcnow()
    })

def get_recent_memories(user_id, limit=15):
    return list(
        memories.find({"user_id": user_id})
        .sort("time", -1)
        .limit(limit)
    )

def summarize_memories(user_id):
    mems = get_recent_memories(user_id, 20)

    summary = []

    for m in mems:
        summary.append(f"{m['role']}: {m['text']}")

    return "\n".join(summary)
