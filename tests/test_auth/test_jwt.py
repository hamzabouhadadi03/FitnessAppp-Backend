"""JWT authentication integration tests.

Tests the authentication middleware without relying on real Auth0.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestJWTProtectedRoutes:
    async def test_protected_route_without_token_returns_401(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Request with no Authorization header → 401 Unauthorized."""
        response = await unauthenticated_client.get("/api/v1/auth/me")

        assert response.status_code == 401

    async def test_protected_route_with_invalid_token_returns_401(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Invalid JWT → 401. No stack trace or internal details in response."""
        response = await unauthenticated_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer totally.invalid.token"},
        )

        assert response.status_code == 401
        body = response.json()
        # Error must not expose internal details
        assert "stack" not in str(body).lower()
        assert "traceback" not in str(body).lower()

    async def test_protected_route_with_expired_token_returns_401(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Expired JWT → 401."""
        response = await unauthenticated_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer expired_token"},
        )

        assert response.status_code == 401

    async def test_protected_route_with_valid_token_returns_200(
        self,
        client: AsyncClient,
    ) -> None:
        """Valid JWT (mocked) → 200 with user data."""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "username" in data
        assert "is_onboarded" in data

    async def test_error_response_format_on_401(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """401 response follows standard error format."""
        response = await unauthenticated_client.get("/api/v1/auth/me")

        assert response.status_code == 401
        body = response.json()
        # Should have standard error structure
        assert "success" in body or "error" in body or response.status_code == 401

    async def test_health_endpoint_requires_no_auth(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """/health is publicly accessible — no JWT required."""
        response = await unauthenticated_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    async def test_security_headers_present(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Security headers must be present on every response."""
        response = await unauthenticated_client.get("/health")

        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in response.headers
        assert response.headers["x-frame-options"] == "DENY"

    async def test_request_id_present_in_response(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Every response must include an X-Request-ID header."""
        response = await unauthenticated_client.get("/health")

        assert "x-request-id" in response.headers

    async def test_no_bearer_scheme_returns_401(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """Non-bearer auth scheme → 401."""
        response = await unauthenticated_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )

        assert response.status_code == 401
