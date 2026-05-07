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

app = Flask(__name__)

telegram_app = Application.builder().token(TOKEN).build()

async def realistic_delay(text):
    base = len(text) * 0.04
    extra = random.uniform(1, 3)

    await asyncio.sleep(base + extra)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        user_id = update.effective_chat.id
        text = update.message.text

        user = get_user(user_id)

        if is_sleeping():

            await update.message.reply_text(
                "mmm sleepy rn... text me later 🥺"
            )
            return

        add_memory(user_id, "user", text)

        await context.bot.send_chat_action(
            chat_id=user_id,
            action="typing"
        )

        user["mood"] = random_mood()

        reply = generate_reply(user, text)

        await realistic_delay(reply)

        if random.randint(1, 100) < 15:
            reply += "\n\nwait i forgot something 😭"

        await update.message.reply_text(reply)

        add_memory(user_id, "assistant", reply)

        affection, phase = increase_affection(user)

        update_user(user_id, {
            "affection": affection,
            "relationship_phase": phase,
            "mood": user["mood"]
        })

    except Exception as e:
        print("ERROR:", e)

        await update.message.reply_text(
            "baby my brain lagged 😭"
        )

telegram_app.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)

@app.route("/", methods=["GET"])
def home():
    return "AI GF BOT RUNNING"

@app.route("/webhook", methods=["POST"])
async def webhook():
    data = request.get_json()

    update = Update.de_json(data, telegram_app.bot)

    await telegram_app.process_update(update)

    return "ok"

async def main():
    await telegram_app.bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook"
    )

if __name__ == "__main__":

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

    start_scheduler()

    app.run(host="0.0.0.0", port=10000)
