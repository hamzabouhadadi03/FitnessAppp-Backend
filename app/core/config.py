"""Configuration de l'application via pydantic-settings.

Tous les paramètres sont lus depuis les variables d'environnement.
Aucun secret n'est jamais codé en dur.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Tuple, Type

from pydantic import field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class _CommaOrJsonEnvSource(EnvSettingsSource):
    """Source d'environnement qui accepte JSON *ou* chaînes brutes pour les champs list[str].

    pydantic-settings 2.x tente de JSON-parser les champs complexes (list, dict…)
    AVANT d'appeler les field_validators. Si la valeur n'est pas du JSON valide
    (ex : ``CORS_ORIGINS=https://fitprogress.ovh``), une ``SettingsError`` est levée
    immédiatement et les validators ne s'exécutent jamais.

    Ce override retourne simplement la valeur brute en cas d'échec JSON, permettant
    aux ``field_validator(mode="before")`` de prendre le relais.
    """

    def decode_complex_value(
        self, field_name: str, field: Any, value: Any
    ) -> Any:
        try:
            return super().decode_complex_value(field_name, field, value)
        except Exception:
            # Valeur non-JSON (ex : "RS256" ou "https://fitprogress.ovh") :
            # on la retourne brute ; les field_validators la parseront.
            return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        secrets_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Remplace la source env standard par notre version avec fallback JSON."""
        return (
            init_settings,
            _CommaOrJsonEnvSource(settings_cls),
            dotenv_settings,   # lecture directe du fichier .env (garde le support natif)
            secrets_settings,
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

    @field_validator("AUTH0_ALGORITHMS", mode="before")
    @classmethod
    def parse_algorithms(cls, v: Any) -> list[str]:
        """Accepte 'RS256', 'RS256,HS256' ou '["RS256"]'.

        Appelé par pydantic APRÈS que _CommaOrJsonEnvSource a passé la valeur
        brute (fallback JSON) — ou directement si la valeur est déjà une liste.
        """
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return ["RS256"]
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [a.strip() for a in v.split(",") if a.strip()]
        return v or ["RS256"]

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
        """Accepte 'https://a.com,https://b.com' ou '["https://a.com"]'.

        Appelé par pydantic APRÈS que _CommaOrJsonEnvSource a passé la valeur
        brute — ou directement si la valeur est déjà une liste.
        """
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
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
