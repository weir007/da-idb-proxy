from fastapi import APIRouter, status
from datetime import datetime

router = APIRouter(prefix="/common", tags=["Common"])


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """健康检查接口 (GET /api/v1/common/health)"""
    return {
        "status": "healthy",
        "code": 200,
        "timestamp": datetime.utcnow().isoformat()
    }
