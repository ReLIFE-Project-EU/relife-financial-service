import time

from fastapi import APIRouter

from relife_financial.config.logging import get_logger

router = APIRouter(tags=["health"])

logger = get_logger(__name__)


@router.get("/health")
async def health_check():
    """Basic health check endpoint that returns service status and current timestamp."""

    return {"status": "healthy", "timestamp": int(time.time())}
