import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


SESSION_COOKIE_NAME = "gdep_session"
SESSION_DURATION_HOURS = 12
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
PBKDF2_ITERATIONS = 120_000


def _app_secret() -> bytes:
    secret = os.getenv("APP_SECRET", "dev-only-change-me-gdep-secret")
    return secret.encode("utf-8")


def _fernet() -> Fernet:
    key_material = hashlib.sha256(_app_secret()).digest()
    key = base64.urlsafe_b64encode(key_material)
    return Fernet(key)


def hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return base64.b64encode(digest).decode("utf-8"), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    computed_hash, _ = hash_password(password, salt=salt)
    return hmac.compare_digest(computed_hash, password_hash)


def validate_password_strength(password: str) -> Optional[str]:
    if len(password) < 10:
        return "A senha deve ter pelo menos 10 caracteres."
    if password.lower() == password or password.upper() == password:
        return "A senha deve combinar letras maiúsculas e minúsculas."
    if not any(char.isdigit() for char in password):
        return "A senha deve conter pelo menos um número."
    if password.isalnum():
        return "A senha deve conter pelo menos um caractere especial."
    return None


def create_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiration() -> datetime:
    return datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
