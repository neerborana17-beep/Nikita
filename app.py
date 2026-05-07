from telegram.ext import (
    Updater,
    MessageHandler,
    Filters
)

from ai_engine import generate_reply
from memory_engine import (
    get_user,
    update_user,
    add_memory
)

from relationship_engine import increase_affection
from routine_engine import is_sleeping
from mood_engine import random_mood
from scheduler import start_scheduler

from dotenv import load_dotenv

import random
import time
import os

# =========================
# LOAD ENV VARIABLES
# =========================

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

# =========================
# VALIDATE TOKEN
# =========================

if not TOKEN:
    raise Exception("Missing TELEGRAM_BOT_TOKEN")

# =========================
# CREATE TELEGRAM BOT
# =========================

updater = Updater(
    TOKEN,
    use_context=True
)

dispatcher = updater.dispatcher

# =========================
# PRIVATE ACCESS SYSTEM
# =========================

def is_allowed(user_id):
    return user_id == ALLOWED_USER_ID

# =========================
# REALISTIC TYPING DELAY
# =========================

def realistic_delay(text):

    base = len(text) * 0.04
    extra = random.uniform(1, 2)

    time.sleep(base + extra)

# =========================
# MESSAGE HANDLER
# =========================

def handle_message(update, context):

    try:

        user_id = update.effective_chat.id

        if not update.message:
            return

        text = update.message.text

        # =========================
        # ACCESS CONTROL
        # =========================

        if not is_allowed(user_id):

            update.message.reply_text(
                "Access denied."
            )

            return

        # =========================
        # LOAD USER
        # =========================

        user = get_user(user_id)

        # =========================
        # SLEEP MODE
        # =========================

        if is_sleeping():

            sleepy_replies = [
                "mmm sleepy rn 🥺",
                "baby i'm trying to sleep",
                "talk tomorrow 😭",
                "half asleep rn"
            ]

            update.message.reply_text(
                random.choice(sleepy_replies)
            )

            return

        # =========================
        # SAVE USER MEMORY
        # =========================

        add_memory(
            user_id,
            "user",
            text,
            tags=["chat", "message"]
        )

        # =========================
        # TYPING ACTION
        # =========================

        context.bot.send_chat_action(
            chat_id=user_id,
            action="typing"
        )

        # =========================
        # RANDOM MOOD
        # =========================

        user["mood"] = random_mood()

        # =========================
        # GENERATE AI RESPONSE
        # =========================

        reply = generate_reply(
            user,
            text
        )

        # =========================
        # HUMAN-LIKE DELAY
        # =========================

        realistic_delay(reply)

        # =========================
        # DOUBLE TEXTING
        # =========================

        if random.randint(1, 100) < 18:

            reply += random.choice([
                "\n\nwait 😭",
                "\n\nomg typo",
                "\n\nignore that 💀"
            ])

        # =========================
        # SEND REPLY
        # =========================

        update.message.reply_text(reply)

        # =========================
        # SAVE AI MEMORY
        # =========================

        add_memory(
            user_id,
            "assistant",
            reply,
            tags=["reply", user["mood"]]
        )

        # =========================
        # RELATIONSHIP PROGRESSION
        # =========================

        affection, phase = increase_affection(user)

        update_user(
            user_id,
            {
                "affection": affection,
                "relationship_phase": phase,
                "mood": user["mood"]
            }
        )

    except Exception as e:

        print("MESSAGE ERROR:", e)

        try:

            update.message.reply_text(
                "baby my brain lagged 😭"
            )

        except:
            pass

# =========================
# REGISTER MESSAGE HANDLER
# =========================

dispatcher.add_handler(
    MessageHandler(
        Filters.text & ~Filters.command,
        handle_message
    )
)

# =========================
# MAIN FUNCTION
# =========================

def main():

    print("AI GF BOT RUNNING ❤️")

    # START PROACTIVE SCHEDULER
    start_scheduler()

    # START TELEGRAM BOT
    updater.start_polling()

    updater.idle()

# =========================
# RUN APP
# =========================

if __name__ == "__main__":
    main()
