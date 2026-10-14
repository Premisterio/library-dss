from fastapi import APIRouter

from app.api.v1 import auth, meta, system
from app.core.errors import PROBLEM_RESPONSES

api_router = APIRouter(responses=PROBLEM_RESPONSES)
api_router.include_router(system.router)
api_router.include_router(meta.router)
api_router.include_router(auth.router)
