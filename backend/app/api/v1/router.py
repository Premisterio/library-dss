from fastapi import APIRouter

from app.api.v1 import system
from app.core.errors import PROBLEM_RESPONSES

api_router = APIRouter(responses=PROBLEM_RESPONSES)
api_router.include_router(system.router)
