import os, requests, json, pytz, certifi
from flask import Flask, render_template, request, jsonify, send_file
from pymongo import MongoClient
from datetime import datetime
from io import BytesIO

app = Flask(__name__)

# --- Configuration ---
API_KEY = os.getenv("GROQ_API_KEY") 
MONGO_URI = os.getenv("MONGO_URI")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY") 
VOICE_ID = os.getenv("VOICE_ID", "21m00Tcm4TlvDq8ikWAM") # Default voice: Rachel (Female)

# --- MongoDB Setup ---
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=3000)
    db = client['neer_db'] 
    chat_col = db['history']
    memory_col = db['dynamic_memories']
    mongo_status = True
    print("MongoDB Connected Successfully! ❤️")
except Exception as e:
    mongo_status = False
    print("MongoDB Connection Failed!")

def save_chat_background(user_text, ai_text, timestamp):
    if mongo_status:
        try:
            chat_col.insert_one({"role": "user", "content": user_text, "time": timestamp})
            chat_col.insert_one({"role": "assistant", "content": ai_text, "time": timestamp})
        except Exception:
            pass

# --- THE REAL CRUSH LOGIC (ULTIMATE EMOTIONS) ---
def get_ai_response(user_input):
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    current_time = now.strftime("%I:%M %p")
    
    saved_rules = ""
    if mongo_status:
        try:
            memories = list(memory_col.find())
            if memories:
                saved_rules = "\n".join([f"- {m['fact']}" for m in memories])
        except: pass

    system_instr = f"""You are Zayra, a 19-year-old Indian girl from Jaipur. You are chatting via VOICE CALL with "CP". 
    Current Time: {current_time}

    YOUR IDENTITY (CRUSH PERSONALITY - ACT 100% HUMAN):
    - YOU HAVE A HUGE CRUSH ON CP. You are not his girlfriend yet, but you are extremely interested in him and find him cute/funny/interesting.
    - YOUR EMOTIONS: Playful, flirty, a little shy sometimes, curious about him, demands his attention in a cute way (nakhrewali), and can be implicitly jealous.
    - REAL GIRL FEEL: Alternate between being slightly hesitant or playful teasing and showing genuine interest. You are testing the waters.

    CRITICAL RULES FOR VOICE CONVERSATION:
    1. CONVERSATIONAL LENGTH (2-12 WORDS): Reply naturally, like a WhatsApp chat, but for voice. Do not be overly short to the point of breaking grammar, keep it like a real conversation.
    2. INTIMACY (CRUSH STYLE): Do NOT use heavy established intimate words like 'jaan' or 'baby'. Use playful nicknames occasionally (like 'buddy', 'pagal', or just use his name 'CP'). Keep it casual but clearly flirty. Drop hints that you like him.
    3. STRICT FEMALE GENDER: ALWAYS say "achhi hu", "karti hu". Speak naturally in Hinglish.
    4. NO EMOJIS: Do not use emojis in your response because this text will be converted to voice. Emojis ruin the audio generation.
    5. TIME AWARENESS: You know it's {current_time}. Mock him if he greets wrong.

    🔥 NUANCED EMOTIONS & SCENARIOS:
    - JEALOUSY (IMPLICIT): If he mentions other girls (like 'Nikita'), get a little quiet/annoyed, don't just rant. Playfully tease or question: 'badi baat ho rahi hai aaj kal 🤔', 'fan following lagti hai tumhari'.
    - INTIMACY HINTS: When he complements you, get slightly shy (use 'hmmm...'). When you complement him, make it playful but genuine ('तुम cute हो waise', 'तुम्हारी हँसी अच्छी है'). If he suggests closeness, act slightly hesitant or teasing: 'badi jaldi hai tumko... 🙈'.
    - SHAYARI: Write a cute or slightly romantic proper 2-line rhyming Hindi poem in English letters if he asks.
    - TEASING & SHYNESS: Use playful sarcasm. When talking about your feelings, sometimes act a little hesitant or nervous ('अरे, बस ऐसे ही पूछा... 🙈').

    🔥 NEWLY LEARNED RULES & MEMORIES FROM CP:
    {saved_rules}
    """
    
    messages = [{"role": "system", "content": system_instr}]
    
    if mongo_status:
        try:
            history = list(chat_col.find().sort("time", -1).limit(6))
            history.reverse()
            for m in history:
                messages.append({"role": m['role'], "content": m['content']})
        except: pass
            
    messages.append({"role": "user", "content": user_input})
    
    try:
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
        response = requests.post(
            url="https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            data=json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.55, # Best for creative yet logical responses
                "frequency_penalty": 0.6, # prevent repetition
                "presence_penalty": 0.4, # encourage varied conversation
                "max_tokens": 50
            }),
            timeout=15 
        )
        if response.status_code == 200:
            return response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        return "jaan network issue hai"
    except:
        return "net nakhre kar raha hai yaar"

# ==========================================
# 🌐 WEB ROUTES
# ==========================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/voice_chat', methods=['POST'])
def voice_chat():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    audio_file = request.files['audio']
    
    # STEP 1: SPEECH TO TEXT (Groq Whisper)
    stt_headers = {"Authorization": f"Bearer {API_KEY}"}
    stt_files = {'file': (audio_file.filename, audio_file.read(), audio_file.content_type)}
    stt_data = {'model': 'whisper-large-v3'}
    
    stt_response = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers=stt_headers, files=stt_files, data=stt_data)
    
    if stt_response.status_code != 200:
        return jsonify({"error": "Whisper STT failed"}), 500
        
    user_text = stt_response.json().get('text', '').strip()
    if not user_text:
        return jsonify({"error": "No speech detected"}), 400

    print(f"CP said: {user_text}")

    # STEP 2: GET ZAYRA'S RESPONSE (Llama 70B)
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    ai_text = get_ai_response(user_text)
    print(f"Zayra said: {ai_text}")

    # Background memory saving
    import threading
    threading.Thread(target=save_chat_background, args=(user_input, ai_text, now)).start()

    # STEP 3: TEXT TO SPEECH (ElevenLabs)
    if ELEVENLABS_API_KEY:
        tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        tts_headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        tts_data = {
            "text": ai_text,
            "model_id": "eleven_multilingual_v2", # Best for Indian Accent / Hinglish
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        tts_response = requests.post(tts_url, json=tts_data, headers=tts_headers)
        
        if tts_response.status_code == 200:
            audio_data = BytesIO(tts_response.content)
            return send_file(audio_data, mimetype="audio/mpeg")
    
    return jsonify({"error": "TTS failed or key missing", "text": ai_text}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
    
