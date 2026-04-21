from fastapi import APIRouter

from .engagements import router as engagements_router

router = APIRouter()
router.include_router(engagements_router, prefix="/engagements", tags=["engagements"])
