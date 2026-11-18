from app.core.login_throttle import LoginThrottle
from app.core.models.user import User, normalize_email
from app.core.passwords import hash_password, verify_password
from app.core.repositories.users import UserRepository

# Hash giả để vẫn tốn thời gian băm khi email không tồn tại (không lộ email nào có thật).
_DUMMY_HASH = hash_password("khong-ai-dung-mat-khau-nay")


class LoginLockedError(Exception):
    """Sai mật khẩu quá nhiều lần, đang bị khoá tạm."""


def authenticate(
    users: UserRepository, email: str, password: str, throttle: LoginThrottle
) -> User | None:
    """Cho vào nếu email có trong tab Users, đang active và đúng mật khẩu.

    Mọi lý do sai đều trả None (cùng một kết quả) và được đếm vào bộ chống dò.
    """
    email = normalize_email(email)
    if throttle.is_locked(email):
        raise LoginLockedError

    user = users.get(email)
    password_hash = users.get_password_hash(email) if user is not None else ""
    password_ok = verify_password(password, password_hash or _DUMMY_HASH)

    if user is None or not user.active or not password_hash or not password_ok:
        throttle.record_failure(email)
        return None

    throttle.reset(email)
    return user


class WrongCurrentPasswordError(Exception):
    """Mật khẩu hiện tại nhập sai khi đổi mật khẩu."""


def change_password(
    users: UserRepository, email: str, current: str, new: str, throttle: LoginThrottle
) -> None:
    """Đổi mật khẩu của chính người đang đăng nhập. Nhập sai mật khẩu cũ cũng tính vào khoá."""
    email = normalize_email(email)
    if throttle.is_locked(email):
        raise LoginLockedError
    if not verify_password(current, users.get_password_hash(email)):
        throttle.record_failure(email)
        raise WrongCurrentPasswordError
    users.set_password_hash(email, hash_password(new))
    throttle.reset(email)
