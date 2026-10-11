"""One error JSON shape for every API failure: { error: { code, message } }."""

from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """Raise this from services and routers when a business rule fails."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def error_body(code: str, message: str) -> Dict[str, Any]:
    """Build the shared error envelope."""
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    """Attach handlers so validation, HTTP, and AppError all look the same."""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = str(exc.detail)
        code = "http_error"
        if exc.status_code == 401:
            code = "unauthorized"
        if exc.status_code == 403:
            code = "forbidden"
        if exc.status_code == 404:
            code = "not_found"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # First message is enough for shop staff; full list is in OpenAPI.
        first = "Invalid request."
        errors = exc.errors()
        if len(errors) > 0:
            item = errors[0]
            loc = item.get("loc", ())
            msg = item.get("msg", first)
            first = str(msg) + " (" + ".".join(str(part) for part in loc) + ")"
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", first),
        )

    @app.exception_handler(JWTError)
    async def jwt_handler(_request: Request, _exc: JWTError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content=error_body("unauthorized", "Invalid or expired token."),
        )
