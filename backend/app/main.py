"""FastAPI application factory (`uvicorn app.main:create_app --factory`)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from scalar_fastapi import get_scalar_api_reference

from app import __version__
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers

API_PREFIX = "/api/v1"


def _operation_id(route: APIRoute) -> str:
    return route.name


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Library DSS API",
        summary="Decision support system for an online library",
        version=__version__,
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=None,
        redoc_url=None,
        generate_unique_id_function=_operation_id,
    )
    app.state.settings = settings
    install_error_handlers(app)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.include_router(api_router, prefix=API_PREFIX)

    @app.get("/api/docs", include_in_schema=False)
    def api_docs() -> HTMLResponse:
        return get_scalar_api_reference(openapi_url=f"{API_PREFIX}/openapi.json", title=app.title)

    return app
