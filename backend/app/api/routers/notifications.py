from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.core.notifications import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationList(BaseModel):
    items: list[Notification]
    unread: int


@router.get("")
def list_notifications(user: CurrentUser, services: ServicesDep) -> NotificationList:
    items = services.notifications.list(user.email)
    return NotificationList(items=items, unread=sum(not item.read for item in items))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(user: CurrentUser, services: ServicesDep) -> None:
    services.notifications.mark_all_read(user.email)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notification_id: str, user: CurrentUser, services: ServicesDep) -> None:
    if not services.notifications.mark_read(user.email, notification_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Không tìm thấy thông báo")
