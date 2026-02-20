def ai_review(text: str):

    score = 0.85
    flags = []

    if "badword" in text.lower():
        flags.append("inappropriate")

    return {
        "score": score,
        "flags": ",".join(flags)
    }


def determine_initial_status(role: str):

    if role == "faculty":
        return "approved", "public"

    if role == "student":
        return "ai_reviewed", "private"

    return "pending", "private"