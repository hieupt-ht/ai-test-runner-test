from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    """Dùng để kiểm tra server còn sống (Docker, người vận hành)."""
    return {"status": "ok"}
