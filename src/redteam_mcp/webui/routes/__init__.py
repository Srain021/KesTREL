from fastapi import APIRouter

from .engagements import router as engagements_router
from .findings import router as findings_router
from .settings import router as settings_router

router = APIRouter()
router.include_router(engagements_router, prefix="/engagements", tags=["engagements"])
router.include_router(
    findings_router,
    prefix="/engagements/{slug}/findings",
    tags=["findings"],
)
router.include_router(settings_router, prefix="/settings", tags=["settings"])
