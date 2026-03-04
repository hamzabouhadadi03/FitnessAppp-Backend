"""Integration tests for gamification endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestGamificationEndpoints:
    async def test_get_stats_authenticated(self, client: AsyncClient) -> None:
        """GET /gamification/stats returns global user stats."""
        response = await client.get("/api/v1/gamification/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_sessions" in data
        assert "total_volume_kg" in data
        assert "total_sets" in data

    async def test_get_streak_authenticated(self, client: AsyncClient) -> None:
        """GET /gamification/streak returns streak info."""
        response = await client.get("/api/v1/gamification/streak")

        assert response.status_code == 200
        data = response.json()
        assert "current_streak_days" in data
        assert "longest_streak_days" in data

    async def test_get_personal_records_authenticated(self, client: AsyncClient) -> None:
        """GET /gamification/personal-records returns list of PRs."""
        response = await client.get("/api/v1/gamification/personal-records")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_progress_score_authenticated(self, client: AsyncClient) -> None:
        """GET /gamification/progress-score returns 0-100 score."""
        response = await client.get("/api/v1/gamification/progress-score")

        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert 0 <= data["score"] <= 100

    async def test_get_activity_history_authenticated(self, client: AsyncClient) -> None:
        """GET /gamification/activity-history returns heatmap data."""
        response = await client.get("/api/v1/gamification/activity-history")

        assert response.status_code == 200
        data = response.json()
        assert "weeks" in data
        assert isinstance(data["weeks"], list)

    async def test_gamification_endpoints_require_auth(
        self,
        unauthenticated_client: AsyncClient,
    ) -> None:
        """All gamification endpoints require authentication."""
        endpoints = [
            "/api/v1/gamification/stats",
            "/api/v1/gamification/streak",
            "/api/v1/gamification/personal-records",
            "/api/v1/gamification/progress-score",
            "/api/v1/gamification/activity-history",
        ]

        for endpoint in endpoints:
            response = await unauthenticated_client.get(endpoint)
            assert response.status_code == 401, f"Expected 401 for {endpoint}"
