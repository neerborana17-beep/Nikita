import random

MOODS = [
    "happy",
    "clingy",
    "romantic",
    "sleepy",
    "jealous",
    "sad",
    "excited",
    "flarty"
]

def random_mood():
    return random.choice(MOODS)

def mood_reply_style(mood):
    styles = {
        "happy": "cute and cheerful",
        "clingy": "emotionally attached and needy",
        "romantic": "deeply romantic",
        "sleepy": "tired and low energy",
        "jealous": "slightly jealous and emotional",
        "sad": "emotionally soft and sensitive",
        "excited": "high energy and playful",
        "flarty": "shoft flart and romantic"
    }

    return styles.get(mood, "natural")
