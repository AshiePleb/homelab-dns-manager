import base64
import hashlib
import secrets

from cryptography.fernet import Fernet
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone

from app.config import get_settings

settings = get_settings()

# Argon2id for new passwords; bcrypt verified for existing hashes (auto-upgraded on login).
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated=["bcrypt"],
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
    bcrypt__rounds=12,
)


def _get_fernet() -> Fernet:
    key_material = settings.encryption_key.encode()
    if len(key_material) < 32:
        key_material = hashlib.sha256(key_material).digest()
    else:
        key_material = hashlib.sha256(key_material).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def password_needs_rehash(hashed: str) -> bool:
    return pwd_context.needs_update(hashed)


def create_access_token(
    data: dict,
    session_id: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta or timedelta(minutes=settings.session_expire_minutes)
    )
    to_encode = {
        **data,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": expire,
        "type": "session",
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "sid"]},
        )
        if payload.get("type") != "session":
            return None
        return payload
    except JWTError:
        return None


def encrypt_value(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    return _get_fernet().decrypt(value.encode()).decode()


API_KEY_PREFIX = "hld_"


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix_for_display, hash)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"{API_KEY_PREFIX}{raw}"
    prefix = full_key[:12]
    key_hash = hash_api_key(full_key)
    return full_key, prefix, key_hash


def hash_api_key(key: str) -> str:
    material = f"{settings.jwt_secret_key}:{key}".encode()
    return hashlib.sha256(material).hexdigest()


def verify_api_key(key: str, key_hash: str) -> bool:
    return hash_api_key(key) == key_hash


def is_api_key_token(token: str) -> bool:
    return token.startswith(API_KEY_PREFIX)
