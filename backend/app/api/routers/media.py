"""Ký upload Cloudinary cho tester (ảnh/video hướng dẫn trong case)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.media_upload import require_storage, upload_to_drive
from app.api.project_access import load_project
from app.core.media.cloudinary import SignedUpload
from app.core.models.media import NOT_CONFIGURED, Media, MediaKind
from app.core.permissions import Action

router = APIRouter(prefix="/api/projects/{project_id}/media", tags=["media"])


class SignRequest(BaseModel):
    kind: MediaKind
    # Tester chỉ được tải lên thư mục hướng dẫn; thư mục bằng chứng dành cho agent
    purpose: Literal["guide"]


@router.post("/sign", response_model=SignedUpload)
def sign_upload(
    project_id: str, body: SignRequest, user: CurrentUser, services: ServicesDep
) -> SignedUpload:
    project = load_project(services, user, project_id, Action.EDIT_TEST_CASE)
    require_storage(project, "cloudinary")
    if services.cloudinary_signer is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_CONFIGURED)
    return services.cloudinary_signer.sign(project.id, body.purpose, body.kind)


@router.post("/upload", response_model=Media)
def upload_media(
    project_id: str,
    file: UploadFile,
    user: CurrentUser,
    services: ServicesDep,
    # Giống /sign: tester chỉ được tải lên thư mục hướng dẫn
    purpose: Annotated[Literal["guide"], Form()] = "guide",
) -> Media:
    """Dự án lưu ở Google Drive: backend nhận file rồi đẩy lên Drive."""
    project = load_project(services, user, project_id, Action.EDIT_TEST_CASE)
    return upload_to_drive(services, project, purpose, file)
