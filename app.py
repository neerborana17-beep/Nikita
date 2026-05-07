from flask import Flask, request
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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

app = Flask(__name__)

telegram_app = Application.builder().token(TOKEN).build()

# =========================
# REALISTIC TYPING DELAY
# =========================

async def realistic_delay(text):
    base = len(text) * 0.045
    extra = random.uniform(1, 3)

    await asyncio.sleep(base + extra)

# =========================
# ACCESS CONTROL
# =========================

def is_allowed(user_id):
    return user_id == ALLOWED_USER_ID

# =========================
# MAIN MESSAGE HANDLER
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        user_id = update.effective_chat.id
        text = update.message.text

        # =========================
        # ALLOWED USER CHECK
        # =========================

        if not is_allowed(user_id):

            await update.message.reply_text(
                "Access denied."
            )

            return

        user = get_user(user_id)

        # =========================
        # SLEEP SYSTEM
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
        # SAVE USER MESSAGE
        # =========================

        add_memory(
            user_id,
            "user",
            text,
            tags=["chat", "user_message"]
        )

        # =========================
        # TYPING SIMULATION
        # =========================

        await context.bot.send_chat_action(
            chat_id=user_id,
            action="typing"
        )

        # =========================
        # RANDOM MOOD SYSTEM
        # =========================

        user["mood"] = random_mood()

        # =========================
        # GENERATE AI REPLY
        # =========================

        reply = generate_reply(user, text)

        # =========================
        # REALISTIC DELAY
        # =========================

        await realistic_delay(reply)

        # =========================
        # HUMAN TEXTING MISTAKES
        # =========================

        if random.randint(1, 100) < 20:

            mistakes = [
                "\n\nwait i forgot 😭",
                "\n\nnvm ignore that",
                "\n\nidk why i said that 💀",
                "\n\nomg typo"
            ]

            reply += random.choice(mistakes)

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
            tags=["ai_reply", user["mood"]]
        )

        # =========================
        # RELATIONSHIP PROGRESSION
        # =========================

        affection, phase = increase_affection(user)

        # =========================
        # UPDATE USER STATE
        # =========================

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
# HOME ROUTE
# =========================

@app.route("/", methods=["GET"])
def home():
    return "AI GF BOT RUNNING"

# =========================
# WEBHOOK ROUTE
# =========================

@app.route("/webhook", methods=["POST"])
async def webhook():

    try:

        data = request.get_json()

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        await telegram_app.process_update(update)

        return "ok"

    except Exception as e:

        print("WEBHOOK ERROR:", e)

        return "error"

# =========================
# STARTUP
# =========================

async def main():

    await telegram_app.bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook"
    )

# =========================
# RUN APP
# =========================

if __name__ == "__main__":

    loop = asyncio.get_event_loop()

    loop.run_until_complete(main())

    start_scheduler()

    app.run(
        host="0.0.0.0",
        port=10000
    )
