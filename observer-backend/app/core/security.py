"""Security primitives — cookie encryption (Fernet) and password hashing (argon2id).

Per CONVENTIONS.md §7:
- Cookies encrypted at rest with Fernet
- Passwords hashed with argon2id (never bcrypt)
- Keys read from settings only; never log decrypted values
"""

import json

from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.errors import AuthError

_settings = get_settings()
_fernet = Fernet(_settings.cookie_enc_key.encode())
_pwd = CryptContext(schemes=["argon2"], deprecated="auto")


# ─── cookies ────────────────────────────────────
def encrypt_cookies(cookies: list[dict]) -> bytes:
    """Serialize then encrypt a list of cookie dicts. Output is ciphertext bytes."""
    return _fernet.encrypt(json.dumps(cookies).encode("utf-8"))


def decrypt_cookies(blob: bytes) -> list[dict]:
    """Decrypt and deserialize. Raises AuthError on any key/integrity failure."""
    try:
        raw = _fernet.decrypt(blob)
    except InvalidToken as e:
        raise AuthError("cookie decryption failed") from e
    return json.loads(raw.decode("utf-8"))


# ─── passwords ──────────────────────────────────
def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd.verify(plain, hashed)
    except Exception:
        return False
