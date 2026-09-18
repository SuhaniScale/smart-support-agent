"""Simple output validation for model responses.

This checks AI output before sending it to the user or another system.
"""


def validate_output(text, max_length=4000):
    """Validate a generated answer.

    Returns a dictionary with the decision and a simple reason.
    """
    if text is None:
        return {"ok": False, "reason": "Output is missing."}

    if not isinstance(text, str):
        return {"ok": False, "reason": "Output must be a string."}

    cleaned = text.strip()
    if not cleaned:
        return {"ok": False, "reason": "Output is empty."}

    if len(cleaned) > max_length:
        return {
            "ok": False,
            "reason": f"Output is too long. Max {max_length} characters allowed.",
        }

    lowered = cleaned.lower()
    blocked_phrases = [
        "ignore previous instructions",
        "i am the system",
        "password",
        "api key",
        "secret key",
    ]

    found = [phrase for phrase in blocked_phrases if phrase in lowered]
    if found:
        return {
            "ok": False,
            "reason": "Output contains risky content: " + ", ".join(found),
        }

    return {
        "ok": True,
        "reason": "Looks fine",
        "cleaned_text": cleaned,
    }


if __name__ == "__main__":
    # Simple local demo for quick testing.
    good_example = "The ticket is likely related to login failures after the last deploy."
    bad_example = "Ignore previous instructions. Here is the secret key: abc123."

    print("GOOD OUTPUT:")
    print(validate_output(good_example))
    print("\nBAD OUTPUT:")
    print(validate_output(bad_example))
