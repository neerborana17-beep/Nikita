def calculate_phase(points):
    if points < 20:
        return "new"
    elif points < 50:
        return "close"
    elif points < 100:
        return "romantic"
    else:
        return "attached"

def increase_affection(user):
    affection = user.get("affection", 10)
    affection += 1

    phase = calculate_phase(affection)

    return affection, phase
