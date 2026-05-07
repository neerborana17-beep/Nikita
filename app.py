from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters
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

import asyncio
import random
import os
from dotenv import load_dotenv

# =========================
# LOAD ENV
# =========================

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

# =========================
# VALIDATION
# =========================

if not TOKEN:
    raise Exception("TELEGRAM_BOT_TOKEN missing")

# =========================
# CREATE TELEGRAM APP
# =========================

telegram_app = Application.builder().token(TOKEN).build()

# =========================
# ALLOWED USER CHECK
# =========================

def is_allowed(user_id):
    return user_id == ALLOWED_USER_ID

# =========================
# REALISTIC TYPING DELAY
# =========================

async def realistic_delay(text):

    typing_time = len(text) * 0.04
    extra_delay = random.uniform(1, 2.5)

    await asyncio.sleep(
        typing_time + extra_delay
    )

# =========================
# MESSAGE HANDLER
# =========================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        user_id = update.effective_chat.id

        if not update.message:
            return

        text = update.message.text

        # =========================
        # PRIVATE ACCESS
        # =========================

        if not is_allowed(user_id):

            await update.message.reply_text(
                "Access denied."
            )

            return

        # =========================
        # LOAD USER
        # =========================

        user = get_user(user_id)

        # =========================
        # SLEEP SYSTEM
        # =========================

        if is_sleeping():

            sleepy_texts = [
                "mmm sleepy rn 🥺",
                "baby i'm trying to sleep",
                "can we talk tomorrow 😭",
                "half asleep rn"
            ]

            await update.message.reply_text(
                random.choice(sleepy_texts)
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

        await context.bot.send_chat_action(
            chat_id=user_id,
            action="typing"
        )

        # =========================
        # RANDOM MOOD
        # =========================

        user["mood"] = random_mood()

        # =========================
        # GENERATE REPLY
        # =========================

        reply = generate_reply(
            user,
            text
        )

        # =========================
        # HUMAN-LIKE DELAY
        # =========================

        await realistic_delay(reply)

        # =========================
        # RANDOM DOUBLE TEXT
        # =========================

        if random.randint(1, 100) < 18:

            extra = random.choice([
                "\n\nwait 😭",
                "\n\nomg typo",
                "\n\nignore that 💀",
                "\n\nidk why i said that"
            ])

            reply += extra

        # =========================
        # SEND REPLY
        # =========================

        await update.message.reply_text(reply)

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
        # RELATIONSHIP SYSTEM
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

            await update.message.reply_text(
                "baby my brain lagged 😭"
            )

        except:
            pass

# =========================
# REGISTER HANDLER
# =========================

telegram_app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    )
)

# =========================
# MAIN
# =========================

def main():

    print("AI GF BOT RUNNING ❤️")

    # START SCHEDULER
    start_scheduler()

    # START BOT
    telegram_app.run_polling(
        drop_pending_updates=True
    )

# =========================
# START
# =========================

if __name__ == "__main__":
    main()
