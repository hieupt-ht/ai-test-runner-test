"""Băm và kiểm tra mật khẩu. Chỉ lưu bản băm (argon2), không bao giờ lưu mật khẩu thật."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Đúng mật khẩu thì True. Hash rỗng hoặc sai định dạng thì coi là sai, không ném lỗi."""
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
