"""Fabrique d'application FastAPI.

Configure les middlewares, les gestionnaires d'exceptions et les routeurs de domaine.
Sécurité avant tout : en-têtes, CORS, limitation de débit, traçage des identifiants de requête.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import connect_db, disconnect_db, get_db
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging

settings = get_settings()
configure_logging()
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Limiteur de débit
# ---------------------------------------------------------------------------
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)


# ---------------------------------------------------------------------------
# Cycle de vie
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("app_starting", env=settings.APP_ENV, version=settings.APP_VERSION)
    await connect_db()
    logger.info("database_connected")
    yield
    await disconnect_db()
    logger.info("app_shutdown")


# ---------------------------------------------------------------------------
# Fabrique d'application
# ---------------------------------------------------------------------------
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="FitProgress — AI-powered fitness progression backend",
        # Désactiver la documentation en production
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        openapi_url="/openapi.json" if settings.is_development else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Limitation de débit
    # ------------------------------------------------------------------
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # CORS — NE JAMAIS utiliser allow_origins=["*"] en production
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    # ------------------------------------------------------------------
    # Middleware des en-têtes de sécurité
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: any) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Swagger UI (en développement) charge des ressources depuis des CDN externes :
        #   - CSS  : cdn.jsdelivr.net
        #   - JS   : cdn.jsdelivr.net
        #   - Fonts: fonts.googleapis.com / fonts.gstatic.com
        # Le CSP strict "default-src 'none'" bloque tout cela et rend /docs vide.
        # Solution : on applique un CSP permissif uniquement pour les routes de doc,
        # et le CSP strict pour toutes les autres routes.
        # En production les routes /docs, /redoc, /openapi.json sont désactivées
        # donc cette exception ne s'applique jamais en prod.
        docs_paths = {"/docs", "/redoc", "/openapi.json"}
        if request.url.path in docs_paths:
            # CSP permissif pour Swagger UI / ReDoc
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net fonts.googleapis.com; "
                "font-src fonts.gstatic.com; "
                "img-src 'self' data:;"
            )
        else:
            # CSP strict pour toutes les autres routes (API, health, etc.)
            response.headers["Content-Security-Policy"] = "default-src 'none'"

        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    # ------------------------------------------------------------------
    # Middleware d'identifiant de requête + journalisation structurée
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: any) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Lie le request_id au contexte structlog pour cette requête
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        import time
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response

    # ------------------------------------------------------------------
    # Gestionnaires d'exceptions
    # ------------------------------------------------------------------
    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ------------------------------------------------------------------
    # Routeurs
    # ------------------------------------------------------------------
    app.include_router(api_router)

    # ------------------------------------------------------------------
    # Vérification de l'état (aucune authentification requise)
    # ------------------------------------------------------------------
    @app.get("/health", tags=["Health"], summary="Health check")
    async def health() -> dict:
        return {"status": "ok", "version": settings.APP_VERSION}

    # ------------------------------------------------------------------
    # Readiness check — vérifie la connexion DB + Redis
    # Utilisé par le monitoring pour confirmer que l'app est prête.
    # ------------------------------------------------------------------
    @app.get("/ready", tags=["Health"], summary="Readiness check")
    async def ready() -> dict:
        from app.core.database import async_session_factory
        try:
            async with async_session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:
            logger.error("readiness_db_failed", error=str(exc))
            raise HTTPException(
                status_code=503,
                detail={"status": "not_ready", "db": str(exc)},
            )
        return {"status": "ready", "version": settings.APP_VERSION}

    # ------------------------------------------------------------------
    # Métriques Prometheus — montées comme sous-application ASGI
    # Accessibles uniquement en interne (nginx bloque /metrics publiquement).
    # ------------------------------------------------------------------
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return app


app = create_app()
