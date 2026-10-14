from fastapi import APIRouter

from app.api.v1 import analytics, auth, datasets, jobs, meta, system
from app.core.errors import PROBLEM_RESPONSES

api_router = APIRouter(responses=PROBLEM_RESPONSES)
api_router.include_router(system.router)
api_router.include_router(meta.router)
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(jobs.router)
api_router.include_router(analytics.router)
