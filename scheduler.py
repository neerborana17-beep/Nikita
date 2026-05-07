from apscheduler.schedulers.background import BackgroundScheduler
from routine_engine import proactive_message
from memory_engine import users
import requests
import os
import random

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

scheduler = BackgroundScheduler()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, json={
            "chat_id": chat_id,
            "text": text
        }, timeout=10)
    except:
        pass

def proactive_texts():
    all_users = users.find()

    for user in all_users:

        if random.randint(1, 100) < 25:
            send_message(
                user["user_id"],
                proactive_message()
            )

def start_scheduler():
    scheduler.add_job(proactive_texts, "interval", minutes=60)
    scheduler.start()
