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

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

# =========================
# CREATE BOT
# =========================

telegram_app = Application.builder().token(TOKEN).build()

# =========================
# ACCESS CONTROL
# =========================

def is_allowed(user_id):
    return user_id == ALLOWED_USER_ID

# =========================
# REALISTIC DELAY
# =========================

async def realistic_delay(text):

    base = len(text) * 0.045
    extra = random.uniform(1, 3)

    await asyncio.sleep(base + extra)

# =========================
# MAIN HANDLER
# =========================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        user_id = update.effective_chat.id
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
        # GET USER
        # =========================

        user = get_user(user_id)

        # =========================
        # SLEEP MODE
        # =========================

        if is_sleeping():

            sleepy_replies = [
                "mmm sleepy rn 🥺",
                "baby i'm trying to sleep",
                "can we talk tomorrow 😭",
                "half asleep rn"
            ]

            await update.message.reply_text(
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
            tags=["chat", "user_message"]
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
        # REALISTIC DELAY
        # =========================

        await realistic_delay(reply)

        # =========================
        # TEXTING MISTAKES
        # =========================

        if random.randint(1, 100) < 20:

            mistakes = [
                "\n\nwait i forgot 😭",
                "\n\nnvm ignore that",
                "\n\nomg typo",
                "\n\nidk why i said that 💀"
            ]

            reply += random.choice(mistakes)

        # =========================
        # SEND MESSAGE
        # =========================

        await update.message.reply_text(reply)

        # =========================
        # SAVE AI MEMORY
        # =========================

        add_memory(
            user_id,
            "assistant",
            reply,
            tags=["ai_reply", user["mood"]]
        )

        # =========================
        # RELATIONSHIP SYSTEM
        # =========================

        affection, phase = increase_affection(user)

        update_user(user_id, {
            "affection": affection,
            "relationship_phase": phase,
            "mood": user["mood"]
        })

    except Exception as e:

        print("ERROR:", e)

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

    print("AI GF BOT STARTED ❤️")

    # START BACKGROUND SCHEDULER
    start_scheduler()

    # START TELEGRAM POLLING
    telegram_app.run_polling(
        drop_pending_updates=True
    )

# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
