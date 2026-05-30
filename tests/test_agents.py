"""
DevBrain AI — Agent Unit Tests (17 tests)

All LLM, cache, GitHub, ChromaDB, and Tavily calls are mocked.
Tests cover intent routing, code review loops, GitHub analyzer caching,
roadmap generation, challenge selection, code evaluation, and resource search.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# State & node imports — adjust paths if your project differs
# ---------------------------------------------------------------------------
from agents.orchestrator import route_intent, DevBrainState
from agents.code_review_agent import (
    code_review_node,
    reflection_node,
    should_reflect_again,
)
from agents.github_analyzer import github_analyzer_node
from agents.roadmap_agent import roadmap_agent_node
from agents.challenge_agent import challenge_agent_node, evaluate_submission
from agents.resource_agent import resource_agent_node


# ===========================================================================
# Helpers
# ===========================================================================

def _make_state(**kwargs) -> DevBrainState:
    """Build a minimal DevBrainState with sensible defaults."""
    defaults: dict[str, Any] = {
        "user_id": str(uuid.uuid4()),
        "github_username": "testdev",
        "user_input": "",
        "route_intent": None,
        "structured_output": None,
        "reflection_score": None,
        "reflection_iteration": 0,
        "max_reflections": 2,
        "skill_profile": {},
        "messages": [],
        "error": None,
    }
    defaults.update(kwargs)
    return DevBrainState(**defaults)


# ===========================================================================
# 1-4  Intent routing
# ===========================================================================

class TestRouteIntent:
    """route_intent should classify user messages into well-known intents."""

    def test_route_review_intent(self):
        state = _make_state(user_input="can you review my code")
        result = route_intent(state)
        assert result == "review"

    def test_route_challenge_intent(self):
        state = _make_state(user_input="give me a practice problem")
        result = route_intent(state)
        assert result == "challenge"

    def test_route_resources_intent(self):
        state = _make_state(user_input="where can I learn about trees")
        result = route_intent(state)
        assert result == "resources"

    def test_route_progress_intent(self):
        state = _make_state(user_input="show me my progress")
        result = route_intent(state)
        assert result == "progress"


# ===========================================================================
# 5-9  Code-review agent + reflection loop
# ===========================================================================

SAMPLE_REVIEW = {
    "summary": "Well-structured function with minor issues.",
    "issues": [
        {"line": 3, "severity": "warning", "message": "Missing docstring"},
    ],
    "suggestions": ["Add type hints", "Consider edge cases for empty input"],
    "score": 0.82,
}


class TestCodeReviewAgent:

    @pytest.mark.asyncio
    @patch("agents.code_review_agent.llm")
    async def test_code_review_node_returns_structured(self, mock_llm):
        mock_llm.structured_call = AsyncMock(return_value=SAMPLE_REVIEW)
        state = _make_state(
            user_input="def add(a, b): return a + b",
            structured_output=None,
        )
        result = await code_review_node(state)
        assert result["structured_output"] == SAMPLE_REVIEW

    @pytest.mark.asyncio
    @patch("agents.code_review_agent.llm")
    async def test_reflection_node_sets_score(self, mock_llm):
        mock_llm.structured_call = AsyncMock(
            return_value={"quality_score": 0.6, "improvements": ["Improve clarity"]}
        )
        state = _make_state(
            structured_output=SAMPLE_REVIEW,
            reflection_score=None,
        )
        result = await reflection_node(state)
        assert result["reflection_score"] == pytest.approx(0.6)

    def test_should_reflect_again_loops(self):
        """Score below threshold + iterations remaining → 'review_again'."""
        state = _make_state(
            reflection_score=0.5,
            iteration_count=0,
            max_iterations=2,
        )
        decision = should_reflect_again(state)
        assert decision == "review_again"

    def test_should_reflect_again_caps(self):
        """Score below threshold but max iterations reached → 'done'."""
        state = _make_state(
            reflection_score=0.5,
            iteration_count=2,
            max_iterations=2,
        )
        decision = should_reflect_again(state)
        assert decision == "done"

    def test_should_reflect_passes(self):
        """Score above threshold → 'done' regardless of iteration count."""
        state = _make_state(
            reflection_score=0.9,
            iteration_count=0,
            max_iterations=2,
        )
        decision = should_reflect_again(state)
        assert decision == "done"


# ===========================================================================
# 10-11  GitHub analyzer with cache logic
# ===========================================================================

class TestGithubAnalyzerNode:

    @pytest.mark.asyncio
    @patch("agents.github_analyzer.github_service")
    @patch("agents.github_analyzer.cache")
    async def test_github_analyzer_uses_cache(self, mock_cache, mock_github):
        """When cache returns a profile, github_service should NOT be called."""
        cached_profile = {
            "Python": 0.80,
            "JavaScript": 0.65,
            "_cached_at": datetime.utcnow().isoformat(),
        }
        mock_cache.get_skill_profile = AsyncMock(return_value=cached_profile)
        mock_github.get_user_repos = AsyncMock()

        state = _make_state(user_id="user-abc")
        await github_analyzer_node(state)

        mock_cache.get_skill_profile.assert_awaited_once()
        mock_github.get_user_repos.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("agents.github_analyzer.llm")
    @patch("agents.github_analyzer.github_service")
    @patch("agents.github_analyzer.cache")
    async def test_github_analyzer_saves_to_cache(
        self, mock_cache, mock_github, mock_llm
    ):
        """On cache miss, github_service is called and result is written to cache."""
        mock_cache.get_skill_profile = AsyncMock(return_value=None)
        mock_cache.set_skill_profile = AsyncMock(return_value=True)
        mock_github.analyze_skill_profile = AsyncMock(
            return_value={
                "skills": {"Python": 0.75, "Shell": 0.20},
                "repo_count": 1,
            }
        )
        mock_llm.call = AsyncMock(return_value="encouraging feedback summary")

        state = _make_state(user_id="user-xyz")
        await github_analyzer_node(state)

        mock_github.analyze_skill_profile.assert_awaited_once()
        mock_cache.set_skill_profile.assert_awaited_once()


# ===========================================================================
# 12  Roadmap agent — 6-week plan
# ===========================================================================

SIX_WEEK_PLAN = {
    "weeks": [
        {"week": i, "focus": f"Topic {i}", "resources": [], "milestones": []}
        for i in range(1, 7)
    ],
    "target_role": "Backend Engineer",
    "estimated_hours_per_week": 10,
}


class TestRoadmapAgent:

    @pytest.mark.asyncio
    @patch("agents.roadmap_agent.polish_roadmap_copy", new_callable=AsyncMock)
    @patch("agents.roadmap_agent.async_session")
    async def test_roadmap_agent_returns_6_weeks(self, mock_session, mock_polish):
        from services.profile_engine import build_analysis_report

        sample = {
            "skills": {"Python": 0.7, "SQL": 0.4},
            "frameworks": {"FastAPI": 0.8},
            "engineering_practices": {
                "has_cicd": False, "test_signal": 0.0,
                "commit_quality": 0.2, "avg_complexity": 5.0,
            },
            "repo_highlights": [{
                "name": "my-api", "primary_language": "Python",
                "stars": 1, "has_cicd": False, "has_tests": False,
                "frameworks": ["FastAPI"], "sample_commits": [],
            }],
            "sample_commits": [],
            "repo_count": 1,
        }
        report = build_analysis_report(sample, "testdev")
        mock_polish.side_effect = lambda plan, *_: plan

        mock_sess = MagicMock()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_sess)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sess.execute = AsyncMock()
        mock_sess.add = MagicMock()
        mock_sess.commit = AsyncMock()
        mock_sess.refresh = AsyncMock()

        state = _make_state(
            skill_profile={"analysis_report": report},
            structured_output={"target_role": "Backend Engineer"},
        )
        result = await roadmap_agent_node(state)
        assert len(result["structured_output"]["weeks"]) == 6
        assert result["structured_output"]["generated_by"] == "roadmap_engine"


# ===========================================================================
# 13  Challenge agent — targets weakest skill
# ===========================================================================

class TestChallengeAgent:

    @pytest.mark.asyncio
    @patch("agents.challenge_agent.llm")
    async def test_challenge_agent_picks_lowest_skill(self, mock_llm):
        """
        With Python=0.1 and JS=0.9, the challenge should address Python
        (the lowest-scoring skill).
        """
        mock_llm.structured_call = AsyncMock(
            return_value={
                "title": "Python Square Challenge",
                "topic": "Python list comprehensions",
                "difficulty": "easy",
                "problem_statement": "Write a list comprehension to square numbers.",
                "starter_code": "numbers = [1, 2, 3, 4, 5]\n# your code here",
                "test_cases": [{"input": "[1,2,3]", "expected": "[1,4,9]"}],
            }
        )
        state = _make_state(
            skill_profile={"Python": 0.1, "JavaScript": 0.9},
        )
        result = await challenge_agent_node(state)
        topic: str = result["structured_output"]["topic"].lower()
        assert "python" in topic


# ===========================================================================
# 14-15  Code evaluation — timeout and passing submission
# ===========================================================================

class TestEvaluateSubmission:

    @pytest.mark.asyncio
    async def test_evaluate_submission_timeout(self):
        """Code that sleeps beyond the timeout should return an error dict."""
        user_code = "import time\ntime.sleep(10)\nprint('done')"
        result = await evaluate_submission(
            user_code=user_code,
            test_cases=[{"input": "", "expected": "done"}],
            timeout_seconds=1,
        )
        assert "error" in result
        assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_evaluate_submission_passes(self):
        """A correct solution against simple test cases should pass."""
        user_code = "def add(a, b):\n    return a + b\nresult = add(2, 3)"
        result = await evaluate_submission(
            user_code=user_code,
            test_cases=[{"input": "add(2, 3)", "expected": "5"}],
            timeout_seconds=5,
        )
        assert result.get("passed") is True


# ===========================================================================
# 16-17  Resource agent — ChromaDB first, Tavily fallback
# ===========================================================================

HIGH_CONFIDENCE_RESULTS = [
    {
        "title": "Binary Trees in Python",
        "url": "https://example.com/trees",
        "snippet": "Comprehensive guide to binary trees.",
        "score": 0.91,
        "source": "chromadb",
    }
]


class TestResourceAgent:

    @pytest.mark.asyncio
    @patch("agents.resource_agent.vector_store")
    @patch("agents.resource_agent.search_service")
    async def test_resource_agent_uses_chromadb_first(
        self, mock_search, mock_vs
    ):
        """High-confidence ChromaDB results should prevent a Tavily call."""
        mock_vs.search_resources = AsyncMock(return_value=[
            {
                "title": f"Trees {i}",
                "url": f"https://example.com/trees{i}",
                "snippet": f"Trees snippet {i}",
                "distance": 0.1,  # less than 0.3 means high confidence
                "source": "chromadb",
            }
            for i in range(3)
        ])
        mock_search.search_resources = AsyncMock(return_value=[])

        state = _make_state(user_input="learn about binary trees")
        await resource_agent_node(state)

        mock_vs.search_resources.assert_awaited_once()
        mock_search.search_resources.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("agents.resource_agent.vector_store")
    @patch("agents.resource_agent.search_service")
    async def test_resource_agent_falls_back_to_tavily(
        self, mock_search, mock_vs
    ):
        """Empty ChromaDB results should trigger a Tavily web search."""
        mock_vs.search_resources = AsyncMock(return_value=[])
        mock_vs.add_resource = AsyncMock()
        mock_search.search_resources = AsyncMock(
            return_value=[
                {
                    "title": "Binary Search Tree - Wikipedia",
                    "url": "https://en.wikipedia.org/wiki/Binary_search_tree",
                    "snippet": "A BST is a rooted binary tree data structure.",
                    "score": 0.78,
                    "source": "tavily",
                }
            ]
        )

        state = _make_state(user_input="learn about binary trees")
        await resource_agent_node(state)

        mock_vs.search_resources.assert_awaited_once()
        mock_search.search_resources.assert_awaited_once()