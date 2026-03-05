"""Configuration de l'application via pydantic-settings.

Tous les paramètres sont lus depuis les variables d'environnement.
Aucun secret n'est jamais codé en dur.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    APP_NAME: str = "FitProgress"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str
    APP_VERSION: str = "1.0.0"

    # -------------------------------------------------------------------------
    # Base de données
    # -------------------------------------------------------------------------
    DATABASE_URL: str
    POSTGRES_USER: str = "fitprogress"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "fitprogress"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # Paramètres du pool de connexions
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    REDIS_URL: str
    REDIS_JWKS_TTL: int = 3600  # secondes — durée de vie du cache JWKS

    # -------------------------------------------------------------------------
    # Auth0
    # -------------------------------------------------------------------------
    AUTH0_DOMAIN: str
    AUTH0_AUDIENCE: str
    AUTH0_ALGORITHMS: list[str] = ["RS256"]

    @property
    def AUTH0_JWKS_URL(self) -> str:
        return f"https://{self.AUTH0_DOMAIN}/.well-known/jwks.json"

    @property
    def AUTH0_ISSUER(self) -> str:
        return f"https://{self.AUTH0_DOMAIN}/"

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    CORS_ORIGINS: list[str] = []

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # -------------------------------------------------------------------------
    # Limitation de débit
    # -------------------------------------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_WORKOUT_PER_MINUTE: int = 30

    # -------------------------------------------------------------------------
    # Journalisation
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # -------------------------------------------------------------------------
    # Celery (broker + backend = Redis)
    # -------------------------------------------------------------------------
    CELERY_BROKER_URL: str = ""   # défaut : REDIS_URL (calculé dans le validator)
    CELERY_RESULT_BACKEND: str = ""  # défaut : REDIS_URL (calculé dans le validator)

    # -------------------------------------------------------------------------
    # Push notifications — APNs (iOS)
    # -------------------------------------------------------------------------
    APNS_ENABLED: bool = False
    APNS_KEY_ID: str = ""       # Key ID 10 chars depuis Apple Developer Portal
    APNS_TEAM_ID: str = ""      # Team ID 10 chars depuis Apple Developer Portal
    APNS_BUNDLE_ID: str = ""    # Bundle ID de l'app iOS (ex : com.fitprogress.app)
    APNS_PRIVATE_KEY: str = ""  # Contenu du fichier .p8 (AuthKey_XXXX.p8)

    # -------------------------------------------------------------------------
    # Push notifications — FCM (Android)
    # -------------------------------------------------------------------------
    FCM_ENABLED: bool = False
    FCM_PROJECT_ID: str = ""           # Firebase project ID
    FCM_SERVICE_ACCOUNT_JSON: str = "" # JSON du service account Firebase (contenu complet)

    # -------------------------------------------------------------------------
    # Calculé
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.is_production:
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
            if not self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must be set in production")
        # Celery URLs : utilise Redis par défaut si non défini
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        return self


@lru_cache
def get_settings() -> Settings:
    """Retourne les paramètres de l'application mis en cache."""
    return Settings()  # type: ignore[call-arg]
