from app.views.api_router import api_router
from app.views.home import router as home_router
from app.views.loans import router as loans_router
from app.views.stats import router as stats_router

__all__ = [
    "api_router",
    "home_router",
    "loans_router",
    "stats_router",
]
