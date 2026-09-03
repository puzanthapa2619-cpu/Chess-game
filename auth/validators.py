"""Input validators for registration/login."""
import re


def validate_username(u: str):
    if not u:
        return False, "Username is required."
    if len(u) < 4:
        return False, "Username must be at least 4 letters."
    if len(u) > 20:
        return False, "Username must be at most 20 letters."
    if any(ch.isdigit() for ch in u):
        return False, "Username cannot contain numbers."
    # letters and spaces only
    if not re.fullmatch(r"[A-Za-z ]+", u):
        return False, "Username can only contain letters and spaces."
    return True, ""


def validate_email(e: str):
    if not e:
        return False, "Email is required."
    if not re.fullmatch(r"[A-Za-z0-9._%+\-]+@gmail\.com", e):
        return False, "Email must end with @gmail.com"
    return True, ""


def validate_password(p: str):
    if not p or len(p) < 6:
        return False, "Password must be at least 6 characters."
    if not re.search(r"[A-Z]", p):
        return False, "Password must contain at least 1 uppercase letter."
    if not re.search(r"[a-z]", p):
        return False, "Password must contain at least 1 lowercase letter."
    if not re.search(r"[0-9]", p):
        return False, "Password must contain at least 1 number."
    return True, ""


def validate_password_confirm(p: str, c: str):
    if p != c:
        return False, "Passwords do not match."
    return True, ""
