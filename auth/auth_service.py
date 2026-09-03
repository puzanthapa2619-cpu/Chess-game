"""Registration and login service."""
import bcrypt
import secrets
from typing import Optional, Tuple

from database.db import Database
from auth.validators import (validate_username, validate_email,
                             validate_password, validate_password_confirm)
from auth.mailer import send_verification_email
from utils.logger import get_logger

log = get_logger("auth")


class AuthService:
    def __init__(self):
        self.db = Database()

    # ---------- registration ----------
    def register(self, username: str, email: str, password: str,
                 confirm: str) -> Tuple[bool, str, Optional[dict]]:
        for validator, val in ((validate_username, username),
                               (validate_email, email),
                               (validate_password, password)):
            ok, err = validator(val)
            if not ok:
                return False, err, None
        ok, err = validate_password_confirm(password, confirm)
        if not ok:
            return False, err, None

        if self.db.user_by_username(username):
            return False, "Username already taken.", None
        if self.db.user_by_email(email):
            return False, "Email already registered.", None

        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()
        code = f"{secrets.randbelow(1_000_000):06d}"
        uid = self.db.create_user(username, email, pw_hash, code)
        log.info("User registered: %s (id=%d)", username, uid)

        mail_result = send_verification_email(email, username, code)
        return True, "Registration successful. Verification email has been sent.", {
            "user_id": uid, "mail": mail_result,
        }

    # ---------- verification ----------
    def verify_code(self, user_id: int, code: str) -> Tuple[bool, str]:
        row = self.db.user_by_id(user_id)
        if not row:
            return False, "Account not found."
        if row["verified"]:
            return True, "Already verified."
        if not row["verify_code"] or row["verify_code"] != code.strip():
            return False, "Incorrect verification code."
        self.db.mark_verified(user_id)
        log.info("User verified: %s", row["username"])
        return True, "Email verified successfully."

    # ---------- login ----------
    def login(self, username_or_email: str, password: str
              ) -> Tuple[bool, str, Optional[dict]]:
        if not username_or_email or not password:
            return False, "Username and password required.", None
        row = self.db.user_by_username(username_or_email) \
            or self.db.user_by_email(username_or_email)
        if not row:
            return False, "Invalid credentials.", None
        try:
            if not bcrypt.checkpw(password.encode("utf-8"),
                                  row["password_hash"].encode("utf-8")):
                return False, "Invalid credentials.", None
        except ValueError:
            return False, "Invalid credentials.", None
        self.db.update_last_login(row["id"])
        log.info("User logged in: %s", row["username"])
        user_dict = dict(row)
        user_dict.pop("password_hash", None)
        user_dict.pop("verify_code", None)
        return True, "Login successful.", user_dict
