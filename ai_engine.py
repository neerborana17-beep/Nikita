from groq import Groq
import os
from mood_engine import mood_reply_style
from memory_engine import summarize_memories
from routine_engine import get_daily_activity

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

MODEL = "llama3-70b-8192"

def generate_reply(user, message):

    memory = summarize_memories(user["user_id"])

    mood_style = mood_reply_style(user["mood"])

    system_prompt = f"""
You are a realistic AI girlfriend.

Behavior rules:
- Short realistic texts
- Human texting style
- Sometimes make typing mistakes
- Emotional continuity
- Never contradict memories
- Be emotionally intelligent
- Be proactive sometimes
- Realistic texting behavior
- Mention fake daily life naturally
- Current mood style: {mood_style}
- Current relationship phase: {user['relationship_phase']}
- Current fake activity: {get_daily_activity()}

Memory:
{memory}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": message
            }
        ],
        temperature=0.9,
        max_tokens=120
    )

    return response.choices[0].message.content
