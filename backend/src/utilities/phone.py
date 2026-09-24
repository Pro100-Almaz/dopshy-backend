import re


def normalize_kz_phone(value: str) -> str:
    """Return a digits-only Kazakhstan phone in the canonical leading-7 form.

    The bot only strips punctuation, so the proxy also canonicalizes common
    local inputs to prevent one person being represented by both 8... and 7....
    Unknown/non-Kazakhstan lengths remain digits-only for bot-side validation.
    """
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("8"):
        return "7" + digits[1:]
    if len(digits) == 10:
        return "7" + digits
    return digits
