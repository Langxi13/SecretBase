from fastapi import APIRouter
from version import APP_VERSION

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "version": APP_VERSION
        }
    }
