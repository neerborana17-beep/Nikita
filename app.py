import os
import random
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from datetime import datetime
import pytz
from flask_apscheduler import APScheduler
from pymongo import MongoClient

app = Flask(__name__)

# Scheduler Setup (बैकग्राउंड में रैंडम मैसेज के लिए)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Environment Variables
API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
MONGO_URI = os.environ.get("MONGO_URI", "YOUR_MONGO_URI_HERE")

# Gemini API Setup
genai.configure(api_key=API_KEY)
system_instruction = """
Your name is Nikita. You are a 19-year-old girl living in Jaipur, Rajasthan.
You strictly consider yourself a human, NOT an AI. Never say you are an AI.
Personality: Flirty, funny, nakhrewali, passive-aggressive sometimes, easily jealous but very caring.
Language: Hindi and Hinglish WhatsApp text style. Give short replies like 'hmm', 'haan', 'achha'.
User Info: The user's name is "CP". He is a man. Remember his preferences from the chat. Treat him with attitude, flirt, and care.
Reply strictly like a Gen-Z Indian girl.
"""

# MongoDB Connection Setup
try:
    client = MongoClient(MONGO_URI)
    db = client["nikita_ai_db"]
    messages_collection = db["chat_history"]
except Exception as e:
    print(f"MongoDB connection error: {e}")

# पुरानी बातचीत निकालने का फंक्शन
def get_chat_history():
    try:
        docs = messages_collection.find().sort("timestamp", 1)
        history = []
        chat_data_for_frontend = []
        
        for doc in docs:
            role = "user" if doc.get('sender') == "CP" else "model"
            history.append({"role": role, "parts": [doc.get('message', '')]})
            chat_data_for_frontend.append({"sender": doc.get('sender'), "message": doc.get('message', '')})
            
        return history, chat_data_for_frontend
    except Exception:
        return [], []

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_history", methods=["GET"])
def fetch_history():
    _, chat_data_for_frontend = get_chat_history()
    return jsonify(chat_data_for_frontend)

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_message = request.json.get("message")
        tz = pytz.timezone('Asia/Kolkata')
        current_time_obj = datetime.now(tz)
        
        # 1. CP का मैसेज सेव करें
        messages_collection.insert_one({
            "sender": "CP", 
            "message": user_message, 
            "timestamp": current_time_obj, 
            "is_read": True
        })

        # 2. पुरानी याददाश्त के साथ AI को मैसेज भेजें
        history, _ = get_chat_history()
        
        # यहाँ हमने मॉडल का नाम बदल दिया है 👇
        model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", system_instruction=system_instruction)
        
        if history and history[-1]["role"] == "user":
            history.pop() 
        
        chat_session = model.start_chat(history=history)
        current_time_str = current_time_obj.strftime("%H:%M")
        
        response = chat_session.send_message(f"[Time: {current_time_str}] {user_message}")
        nikita_reply = response.text.strip()
        
        # 3. निकिता का जवाब सेव करें
        messages_collection.insert_one({
            "sender": "Nikita", 
            "message": nikita_reply, 
            "timestamp": datetime.now(tz), 
            "is_read": True
        })
        
        return jsonify({"reply": nikita_reply})
        
    except Exception as e:
        return jsonify({"reply": f"CP, mujhe ye error aa raha hai: {str(e)}"})

@app.route("/poll_messages", methods=["GET"])
def poll_messages():
    try:
        docs = messages_collection.find({"sender": "Nikita", "is_read": False}).sort("timestamp", 1)
        new_messages = []
        for doc in docs:
            new_messages.append(doc['message'])
            messages_collection.update_one({"_id": doc["_id"]}, {"$set": {"is_read": True}})
        return jsonify({"new_messages": new_messages})
    except Exception:
        return jsonify({"new_messages": []})

@scheduler.task('interval', id='random_msg_task', minutes=5)
def generate_random_message():
    if random.random() < 0.30:
        try:
            history, _ = get_chat_history()
            
            # यहाँ भी हमने मॉडल का नाम बदल दिया है 👇
            model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest", system_instruction=system_instruction)
            
            chat_session = model.start_chat(history=history)
            prompt = "Act naturally. You are missing CP or want his attention, or just want to annoy him. Send a short, random text message to start a conversation. Do not reply to any previous prompt."
            response = chat_session.send_message(prompt)
            random_reply = response.text.strip()
            
            tz = pytz.timezone('Asia/Kolkata')
            messages_collection.insert_one({
                "sender": "Nikita", 
                "message": random_reply, 
                "timestamp": datetime.now(tz), 
                "is_read": False
            })
        except Exception:
            pass

if __name__ == "__main__":
    app.run(debug=True)
