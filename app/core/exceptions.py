"""Gestionnaires d'exceptions globaux et classes d'exceptions personnalisées.

Ne divulgue jamais les détails internes des erreurs ni les traces de pile aux clients de l'API.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Classes d'exceptions personnalisées
# ---------------------------------------------------------------------------
class AppException(Exception):
    """Exception de base de l'application."""

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(
            message=f"{resource} not found",
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class UnauthorizedError(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Authentication required",
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(AppException):
    def __init__(self) -> None:
        super().__init__(
            message="Access denied",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(AppException):
    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class ValidationError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


class BusinessLogicError(AppException):
    def __init__(self, message: str, code: str = "BUSINESS_LOGIC_ERROR") -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# ---------------------------------------------------------------------------
# Constructeur de réponse d'erreur
# ---------------------------------------------------------------------------
def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
            "request_id": request_id,
        },
    )


# ---------------------------------------------------------------------------
# Gestionnaires d'exceptions
# ---------------------------------------------------------------------------
async def app_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppException)
    logger.warning(
        "app_exception",
        code=exc.code,
        status_code=exc.status_code,
        path=request.url.path,
    )
    return _error_response(request, exc.status_code, exc.code, exc.message)


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    logger.warning("request_validation_error", path=request.url.path)
    # Construit un message lisible à partir des erreurs Pydantic
    errors = exc.errors()
    message = "; ".join(
        f"{' -> '.join(str(loc) for loc in e['loc'])}: {e['msg']}"
        for e in errors
    )
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR",
        message,
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Gestionnaire fourre-tout — ne jamais exposer les détails internes au client."""
    logger.exception(
        "unhandled_exception",
        error_type=type(exc).__name__,
        path=request.url.path,
    )
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_SERVER_ERROR",
        "An unexpected error occurred. Please try again later.",
    )
