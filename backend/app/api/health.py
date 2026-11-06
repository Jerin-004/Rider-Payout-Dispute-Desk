"""Health check endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.tools.payswift_client import get_payswift_client

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Service liveness check."""
    # Check DB
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Check PaySwift
    payswift_ok = await get_payswift_client().health()

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "payswift": "ok" if payswift_ok else "unreachable",
    }
