"""
GitHub Service — fetches repos and builds normalized skill profiles.
Uses PyGitHub (sync) wrapped in asyncio.to_thread for non-blocking calls.
"""

import asyncio
import logging
from datetime import datetime

from github import Github, GithubException

logger = logging.getLogger(__name__)

# Commit count is capped to avoid hitting secondary rate limits.
_COMMIT_COUNT_CAP = 200


class GitHubService:
    def __init__(self) -> None:
        # No default token needed; each call receives its own token.
        pass

    # ------------------------------------------------------------------
    # Internal helper — run sync PyGitHub calls off the event loop
    # ------------------------------------------------------------------

    @staticmethod
    async def _run(fn, *args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_user_repos(self, username: str, token: str) -> list[dict]:
        """
        Return all non-forked repos for *username* authenticated with *token*.

        Each item contains:
          name, language, languages (dict lang→bytes), stars, size,
          updated_at, description, topics
        """
        def _fetch():
            gh = Github(token)
            user = gh.get_user(username)
            repos = []
            for repo in user.get_repos(type="owner"):
                if repo.fork:
                    continue
                try:
                    languages = repo.get_languages()  # dict lang→bytes
                except GithubException:
                    languages = {}

                try:
                    topics = repo.get_topics()
                except GithubException:
                    topics = []

                repos.append(
                    {
                        "name": repo.name,
                        "language": repo.language,
                        "languages": languages,
                        "stars": repo.stargazers_count,
                        "size": repo.size,
                        "updated_at": (
                            repo.updated_at.isoformat()
                            if isinstance(repo.updated_at, datetime)
                            else str(repo.updated_at)
                        ),
                        "description": repo.description or "",
                        "topics": topics,
                    }
                )
            return repos

        return await self._run(_fetch)

    async def analyze_skill_profile(self, username: str, token: str) -> dict:
        """
        Build a normalized skill profile from all non-forked repos.

        Returns:
          {
            "skills": {"Python": 0.82, ...},   # 0.0–1.0
            "repo_count": N,
            "top_languages": ["Python", "TypeScript", ...],
            "primary_language": "Python",
          }

        Scoring:
          - Base: raw language bytes across all repos, normalized by max.
          - Bonus: up to +0.15 per language for popular/starred repos
            (commit count capped at _COMMIT_COUNT_CAP).

        Thresholds (for downstream agents):
          < 0.30  → beginner
          0.30–0.65 → intermediate
          > 0.65  → advanced
        """
        def _fetch_with_commits():
            gh = Github(token)
            user = gh.get_user(username)
            repo_data = []
            for repo in user.get_repos(type="owner"):
                if repo.fork:
                    continue
                try:
                    languages = repo.get_languages()
                except GithubException:
                    languages = {}

                # Commit count — capped to avoid secondary rate limits
                try:
                    commits = repo.get_commits()
                    # totalCount is a PaginatedList lazy attribute
                    count = min(commits.totalCount, _COMMIT_COUNT_CAP)
                except GithubException:
                    count = 0

                repo_data.append(
                    {
                        "languages": languages,
                        "stars": repo.stargazers_count,
                        "commit_count": count,
                    }
                )
            return repo_data

        repos = await self._run(_fetch_with_commits)
        repo_count = len(repos)

        if not repos:
            return {
                "skills": {},
                "repo_count": 0,
                "top_languages": [],
                "primary_language": None,
            }

        # ── Aggregate raw bytes per language ────────────────────────────
        lang_bytes: dict[str, int] = {}
        lang_commit_bonus: dict[str, float] = {}
        lang_star_bonus: dict[str, float] = {}

        for repo in repos:
            stars = repo["stars"]
            commits = repo["commit_count"]
            for lang, nbytes in repo["languages"].items():
                lang_bytes[lang] = lang_bytes.get(lang, 0) + nbytes

                # Bonus weight: stars contribute up to 0.10, commits up to 0.05
                star_w = min(stars / 100, 1.0) * 0.10
                commit_w = min(commits / _COMMIT_COUNT_CAP, 1.0) * 0.05
                lang_star_bonus[lang] = max(lang_star_bonus.get(lang, 0.0), star_w)
                lang_commit_bonus[lang] = max(lang_commit_bonus.get(lang, 0.0), commit_w)

        if not lang_bytes:
            return {
                "skills": {},
                "repo_count": repo_count,
                "top_languages": [],
                "primary_language": None,
            }

        # ── Normalize bytes to 0–1 ───────────────────────────────────────
        max_bytes = max(lang_bytes.values())
        skills: dict[str, float] = {}
        for lang, nbytes in lang_bytes.items():
            base = nbytes / max_bytes
            bonus = lang_star_bonus.get(lang, 0.0) + lang_commit_bonus.get(lang, 0.0)
            skills[lang] = min(round(base + bonus, 4), 1.0)

        sorted_langs = sorted(skills, key=lambda l: skills[l], reverse=True)
        top_languages = sorted_langs[:10]
        primary_language = sorted_langs[0] if sorted_langs else None

        return {
            "skills": skills,
            "repo_count": repo_count,
            "top_languages": top_languages,
            "primary_language": primary_language,
        }

    async def get_user_info(self, token: str) -> dict:
        """
        Return basic profile info for the authenticated user.
        """
        def _fetch():
            gh = Github(token)
            user = gh.get_user()
            return {
                "github_id": user.id,
                "login": user.login,
                "name": user.name or "",
                "avatar_url": user.avatar_url,
                "bio": user.bio or "",
                "public_repos": user.public_repos,
            }

        return await self._run(_fetch)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

github_service = GitHubService()