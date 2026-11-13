from app.core.models.user import User
from app.core.repositories.users import UserRepository


def authenticate(users: UserRepository, email: str) -> User | None:
    """Chỉ cho vào nếu email có trong tab Users và đang active."""
    user = users.get(email)
    if user is None or not user.active:
        return None
    return user
