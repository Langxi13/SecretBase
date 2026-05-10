from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "version": "1.0.0"
        }
    }
