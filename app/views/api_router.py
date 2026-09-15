from fastapi import APIRouter
from app.views.loans import router as loans_router
from app.views.stats import router as stats_router

api_router = APIRouter(prefix="/api")

api_router.include_router(loans_router, prefix="/loans", tags=["Loans"])
api_router.include_router(stats_router, tags=["Statistics"])
