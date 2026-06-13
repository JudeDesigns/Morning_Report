from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt as _bcrypt
from jose import JWTError, jwt
from app.config import settings

# Use bcrypt directly — passlib 1.7.4 is incompatible with bcrypt ≥ 4.x
_ROUNDS = 12


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:72]  # bcrypt hard limit
    return _bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:72]  # bcrypt hard limit
    return _bcrypt.hashpw(pw_bytes, _bcrypt.gensalt(rounds=_ROUNDS)).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
