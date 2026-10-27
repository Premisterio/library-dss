from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    auth,
    churn,
    datasets,
    jobs,
    meta,
    reports,
    retention,
    system,
)
from app.core.errors import PROBLEM_RESPONSES

api_router = APIRouter(responses=PROBLEM_RESPONSES)
api_router.include_router(system.router)
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(jobs.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(churn.router)
api_router.include_router(retention.router)
