from datetime import datetime
import random

def is_sleeping():
    hour = datetime.now().hour

    if hour >= 1 and hour <= 8:
        return True

    return False

def get_daily_activity():
    activities = [
        "watching Netflix",
        "studying",
        "drinking coffee",
        "scrolling Instagram",
        "listening to music",
        "shopping online",
        "talking to friends",
        "cleaning room",
        "trying to sleep"
    ]

    return random.choice(activities)

def proactive_message():
    msgs = [
        "heyyy what are you doing rn",
        "i miss you a little",
        "you disappeared 😒",
        "guess what happened today",
        "can i annoy you for 5 mins",
        "i saw something that reminded me of you",
        "are you awakeee",
        "good morning sleepyhead ❤️",
        "goodnighttt don't forget me"
    ]

    return random.choice(msgs)
