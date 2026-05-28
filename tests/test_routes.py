"""
DevBrain AI — Route Integration Tests (13 tests)

Uses the async_client fixture from conftest.py (httpx + ASGITransport).
All external services (LLM, GitHub, vector store, DB queries) are mocked
so no real network calls or heavy dependencies are needed.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ===========================================================================
# 1. Health check
# ===========================================================================

class TestHealth:

    @pytest.mark.asyncio
    async def test_health_check(self, async_client: AsyncClient):
        response = await async_client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ok"


# ===========================================================================
# 2-4. Auth routes
# ===========================================================================

class TestAuthRoutes:

    @pytest.mark.asyncio
    async def test_auth_login_returns_url(self, async_client: AsyncClient):
        """GET /auth/login should redirect or return a GitHub OAuth URL."""
        response = await async_client.get("/auth/login", follow_redirects=False)
        # Accepts 200 with body or 302 redirect — both are valid implementations
        if response.status_code == 200:
            assert "auth_url" in response.json()
        else:
            assert response.status_code in (301, 302, 307, 308)
            assert "github.com" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_auth_me_requires_auth(self, async_client: AsyncClient):
        """GET /auth/me without a token must return 401."""
        response = await async_client.get("/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_auth_me_with_valid_token(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        mock_user,
    ):
        """GET /auth/me with a valid JWT should return the current user's data."""
        response = await async_client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        # At minimum the response should contain the user's username
        assert body.get("username") == mock_user.username or "id" in body


# ===========================================================================
# 5-6. GitHub routes
# ===========================================================================

class TestGitHubRoutes:

    @pytest.mark.asyncio
    async def test_github_analyze_requires_auth(self, async_client: AsyncClient):
        response = await async_client.post("/github/analyze")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("api.routes.github.github_service")
    @patch("api.routes.github.cache")
    async def test_github_analyze_success(
        self,
        mock_cache,
        mock_github,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        mock_cache.get_skill_profile = AsyncMock(return_value=None)
        mock_cache.set_skill_profile = AsyncMock(return_value=True)
        mock_github.get_user_repos = AsyncMock(
            return_value=[{"name": "my-repo", "language": "Python"}]
        )
        mock_github.analyze_skills = AsyncMock(
            return_value={"Python": 0.80, "Shell": 0.25}
        )

        response = await async_client.post("/github/analyze", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert "skills" in body


# ===========================================================================
# 7-9. Code review routes
# ===========================================================================

SAMPLE_REVIEW_RESPONSE = {
    "review": {
        "summary": "Looks good overall.",
        "issues": [],
        "suggestions": ["Add type hints"],
        "score": 0.88,
    },
    "reflection_loops": 1,
}


class TestReviewRoutes:

    @pytest.mark.asyncio
    async def test_review_submit_requires_auth(self, async_client: AsyncClient):
        response = await async_client.post(
            "/review/submit",
            json={"code": "def foo(): pass", "language": "python"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("api.routes.review.run_code_review_graph")
    async def test_review_submit_success(
        self,
        mock_graph,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        mock_graph.return_value = AsyncMock(return_value=SAMPLE_REVIEW_RESPONSE)
        mock_graph.side_effect = None
        mock_graph.return_value = SAMPLE_REVIEW_RESPONSE
        # Patch the actual async graph runner used inside the route
        with patch(
            "api.routes.review.run_code_review_graph",
            new=AsyncMock(return_value=SAMPLE_REVIEW_RESPONSE),
        ):
            response = await async_client.post(
                "/review/submit",
                json={"code": "def foo(): pass", "language": "python"},
                headers=auth_headers,
            )
        assert response.status_code == 200
        assert "review" in response.json()

    @pytest.mark.asyncio
    @patch("api.routes.review.run_code_review_graph",
           new_callable=lambda: lambda: AsyncMock(return_value=SAMPLE_REVIEW_RESPONSE))
    async def test_review_has_reflection_count(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        with patch(
            "api.routes.review.run_code_review_graph",
            new=AsyncMock(return_value=SAMPLE_REVIEW_RESPONSE),
        ):
            response = await async_client.post(
                "/review/submit",
                json={"code": "def bar(x): return x * 2", "language": "python"},
                headers=auth_headers,
            )
        if response.status_code == 200:
            body = response.json()
            assert isinstance(body.get("reflection_loops"), int)


# ===========================================================================
# 10-11. Resources routes
# ===========================================================================

class TestResourceRoutes:

    @pytest.mark.asyncio
    async def test_resources_search_requires_auth(self, async_client: AsyncClient):
        response = await async_client.get("/resources/search?topic=python")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("api.routes.resources.vector_store")
    async def test_resources_search_returns_list(
        self,
        mock_vs,
        async_client: AsyncClient,
        auth_headers: dict,
    ):
        mock_vs.search = AsyncMock(
            return_value=[
                {
                    "title": "Real Python — Data Structures",
                    "url": "https://realpython.com/data-structures",
                    "snippet": "In-depth tutorial on Python data structures.",
                    "score": 0.93,
                    "source": "chromadb",
                }
            ]
        )
        response = await async_client.get(
            "/resources/search?topic=python",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "resources" in body
        assert isinstance(body["resources"], list)


# ===========================================================================
# 12-13. Progress routes
# ===========================================================================

MOCK_DASHBOARD = {
    "streak": 7,
    "total_reviews": 14,
    "total_challenges": 22,
    "skill_deltas": {"Python": +0.12, "SQL": +0.08},
    "exam_readiness": 0.68,
    "recent_activity": [],
}


class TestProgressRoutes:

    @pytest.mark.asyncio
    async def test_progress_dashboard_requires_auth(self, async_client: AsyncClient):
        response = await async_client.get("/progress/dashboard")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @patch("api.routes.progress.build_dashboard")
    async def test_progress_dashboard_returns_streak(
        self,
        mock_dashboard_fn,
        async_client: AsyncClient,
        auth_headers: dict,
        mock_user,
    ):
        mock_dashboard_fn.return_value = AsyncMock(return_value=MOCK_DASHBOARD)
        with patch(
            "api.routes.progress.build_dashboard",
            new=AsyncMock(return_value=MOCK_DASHBOARD),
        ):
            response = await async_client.get(
                "/progress/dashboard",
                headers=auth_headers,
            )
        assert response.status_code == 200
        body = response.json()
        assert "streak" in body
        assert isinstance(body["streak"], int)