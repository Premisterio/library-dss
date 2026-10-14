"""RFC 9457 Problem Details: one machine-readable error format for every client.

Every error carries a stable `code` (e.g. `dataset.not_ready`), so any frontend can map
it to its own message without parsing human-readable text.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"


class FieldError(BaseModel):
    loc: list[str | int] = Field(description="Path to the invalid field, e.g. ['body', 'email'].")
    msg: str
    type: str


class Problem(BaseModel):
    """Error response (RFC 9457 Problem Details) with a stable machine-readable code."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    code: str = Field(description="Stable error code, e.g. `dataset.not_ready`.")
    errors: list[FieldError] = Field(default_factory=list)


class ApiError(Exception):
    """Raise from any layer to return a Problem response."""

    def __init__(
        self,
        status: int,
        code: str,
        detail: str | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail
        self.headers = (
            headers
            if headers is not None
            else ({"WWW-Authenticate": "Bearer"} if status == 401 else None)
        )


# Documented on every route, so generated clients know the error shape.
PROBLEM_RESPONSES: dict[int | str, dict] = {
    422: {"model": Problem, "description": "Request validation failed"},
    "default": {"model": Problem, "description": "Error (RFC 9457 Problem Details)"},
}
# The same for routes whose success response is not JSON (event streams, files): FastAPI would
# otherwise document their errors under the success media type.
PROBLEM_REF = "#/components/schemas/Problem"
PROBLEM_JSON_RESPONSES: dict[int | str, dict] = {
    status: {
        "description": spec["description"],
        "content": {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": PROBLEM_REF}}},
    }
    for status, spec in PROBLEM_RESPONSES.items()
}


def document_problem_media_type(openapi: dict[str, Any]) -> None:
    """Problems are sent as application/problem+json; FastAPI documents them as JSON."""
    for path_item in openapi.get("paths", {}).values():
        for operation in path_item.values():
            for response in operation.get("responses", {}).values():
                content = response.get("content", {})
                if content.get("application/json", {}).get("schema", {}).get("$ref") == PROBLEM_REF:
                    content[PROBLEM_MEDIA_TYPE] = content.pop("application/json")


def _snake(phrase: str) -> str:
    return phrase.lower().replace(" ", "_").replace("-", "_").replace("'", "")


def problem_response(problem: Problem, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        problem.model_dump(mode="json"),
        status_code=problem.status,
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def _allowed_methods(request: Request) -> str:
    """Every method of every route at this path (Starlette only lists the first route's)."""
    methods: set[str] = set()
    for route in request.app.router.routes:
        match, _ = route.matches(request.scope)
        if match is not Match.NONE:
            methods |= getattr(route, "methods", None) or set()
    return ", ".join(sorted(methods))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return problem_response(
            Problem(
                title=HTTPStatus(exc.status).phrase,
                status=exc.status,
                detail=exc.detail,
                code=exc.code,
            ),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            FieldError(loc=list(e.get("loc", ())), msg=e.get("msg", ""), type=e.get("type", ""))
            for e in exc.errors()
        ]
        return problem_response(
            Problem(
                title="Unprocessable Content",
                status=422,
                detail="Request validation failed",
                code="request.invalid",
                errors=errors,
            )
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        phrase = HTTPStatus(exc.status_code).phrase
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail != phrase else None
        headers = getattr(exc, "headers", None)
        if exc.status_code == 405:
            headers = {**(headers or {}), "Allow": _allowed_methods(request)}
        return problem_response(
            Problem(
                title=phrase, status=exc.status_code, detail=detail, code=f"http.{_snake(phrase)}"
            ),
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return problem_response(
            Problem(title="Internal Server Error", status=500, code="server.error")
        )
