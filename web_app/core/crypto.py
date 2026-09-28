"""
crypto.py — Symmetric field encryption for sensitive credentials.
Uses AES-128 in CBC mode with HMAC-SHA256 (Fernet) derived from Django's SECRET_KEY.
Gracefully handles legacy plaintext values for seamless migration.
"""

import os
import base64
import hashlib
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """Derive a deterministic 32-byte urlsafe-base64 Fernet key from Django SECRET_KEY."""
    raw_key = os.environ.get('ENCRYPTION_KEY', settings.SECRET_KEY).encode('utf-8')
    key = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
    return Fernet(key)


def encrypt_value(plain_text: str) -> str:
    """Encrypt a plaintext string and return base64 ciphertext token."""
    if not plain_text:
        return ""
    # If already encrypted token, don't double-encrypt
    if plain_text.startswith("gAAAAA"):
        try:
            _get_fernet().decrypt(plain_text.encode('utf-8'))
            return plain_text
        except InvalidToken:
            pass
    fernet = _get_fernet()
    return fernet.encrypt(plain_text.encode('utf-8')).decode('utf-8')


def decrypt_value(cipher_text: str) -> str:
    """
    Decrypt a ciphertext token.
    If the value is unencrypted legacy text, returns it as-is without raising an error.
    """
    if not cipher_text:
        return ""
    if not cipher_text.startswith("gAAAAA"):
        return cipher_text
    try:
        fernet = _get_fernet()
        return fernet.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
    except (InvalidToken, Exception):
        # Fall back to raw string if token is invalid or legacy
        return cipher_text


def mask_value(value: str, visible_tail: int = 4) -> str:
    """Mask a secret value for safe display in UI/logs (e.g. ••••••••abcd)."""
    if not value:
        return ""
    decrypted = decrypt_value(value)
    if len(decrypted) <= visible_tail:
        return "•" * len(decrypted)
    return "•" * (len(decrypted) - visible_tail) + decrypted[-visible_tail:]
