"""Ký upload Cloudinary cho tester (ảnh/video hướng dẫn trong case)."""

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, ServicesDep
from app.api.project_access import load_project
from app.core.media.cloudinary import SignedUpload
from app.core.models.media import NOT_CONFIGURED, MediaKind
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
    if services.cloudinary_signer is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NOT_CONFIGURED)
    return services.cloudinary_signer.sign(project.id, body.purpose, body.kind)
