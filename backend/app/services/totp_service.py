"""TOTP two-factor authentication."""

from __future__ import annotations

import pyotp

from app.core.security import decrypt_value, encrypt_value


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, username: str, issuer: str = "HomeLab DNS Manager") -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def verify_totp(secret_plain: str, code: str) -> bool:
    if not secret_plain or not code:
        return False
    totp = pyotp.TOTP(secret_plain)
    return totp.verify(code.strip(), valid_window=1)


def store_totp_secret(secret: str) -> str:
    return encrypt_value(secret)


def read_totp_secret(encrypted: str | None) -> str | None:
    if not encrypted:
        return None
    try:
        return decrypt_value(encrypted)
    except Exception:
        return None
