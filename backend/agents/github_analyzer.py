"""
GitHub Analyzer Agent
=====================
Fetches a user's public GitHub repositories, builds a skill profile, writes a
narrative summary via Grok, caches the result in Redis, and persists it to
PostgreSQL.

Route file can import SkillProfileResponse from here.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select

from core.config import settings
from models.database import async_session
from models.skill_profile import SkillProfile
from services.cache_service import cache
from services.github_service import github_service
from services.llm_service import llm

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════ #
# Pydantic response schema (used by the /github routes)                       #
# ═══════════════════════════════════════════════════════════════════════════ #


class SkillProfileResponse(BaseModel):
    user_id: str
    github_username: str
    skills: dict[str, float]
    summary: str
    repo_count: int
    analyzed_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════ #
# Agent node                                                                  #
# ═══════════════════════════════════════════════════════════════════════════ #


async def github_analyzer_node(state: dict) -> dict:
    """
    LangGraph node: analyse a developer's GitHub repos and build a skill profile.

    Steps
    -----
    1. Check Redis cache.
    2. If cache miss → call github_service.analyze_skill_profile().
    3. Ask Grok for a 3-sentence narrative summary.
    4. Store in Redis (24 h TTL) and upsert into PostgreSQL.
    5. Populate state["structured_output"] and state["agent_output"].
    """
    user_id: str = state["user_id"]
    github_username: str = state["github_username"]

    try:
        # ── 1. Cache lookup ────────────────────────────────────────────────
        cached = await cache.get_skill_profile(user_id)
        if cached:
            logger.info("Cache hit for skill profile user_id=%s", user_id)
            skills: dict[str, float] = cached.get("skills", {})
            repo_count: int = cached.get("repo_count", 0)
            summary: str = cached.get("summary", "")
        else:
            # ── 2. Fetch from GitHub ───────────────────────────────────────
            # Allow a caller-provided token (passed via user_input field)
            token: Optional[str] = None
            raw_input: str = state.get("user_input", "")
            if raw_input.startswith("ghp_") or raw_input.startswith("github_pat_"):
                token = raw_input.strip()
            else:
                token = getattr(settings, "GITHUB_PAT", None)

            profile_data: dict = await github_service.analyze_skill_profile(
                github_username, token
            )
            skills = profile_data.get("skills", {})
            repo_count = profile_data.get("repo_count", 0)

            # ── 3. LLM narrative summary ───────────────────────────────────
            skill_lines = "\n".join(
                f"  {lang}: {score:.2f}" for lang, score in sorted(
                    skills.items(), key=lambda x: x[1], reverse=True
                )[:10]
            )
            prompt = (
                f"You are a senior engineering career coach.\n"
                f"A developer named '{github_username}' has the following language "
                f"proficiency scores derived from their GitHub repositories "
                f"(0 = no experience, 1 = expert):\n\n"
                f"{skill_lines}\n\n"
                f"Write exactly 3 sentences that:\n"
                f"1. Describe their primary technical strengths.\n"
                f"2. Identify one clear gap or growth area.\n"
                f"3. Give one actionable career recommendation.\n"
                f"Be encouraging, specific, and concise."
            )
            summary = await llm.complete(prompt)

            # ── 4a. Store in Redis (24 h) ──────────────────────────────────
            await cache.set_skill_profile(
                user_id,
                {"skills": skills, "repo_count": repo_count, "summary": summary},
                ttl=86_400,
            )

        # ── 4b. Upsert SkillProfile in PostgreSQL ──────────────────────────
        async with async_session() as session:
            result = await session.execute(
                select(SkillProfile).where(SkillProfile.user_id == uuid.UUID(user_id))
            )
            existing: Optional[SkillProfile] = result.scalar_one_or_none()

            if existing:
                existing.skills = skills
                existing.repo_count = repo_count
                existing.summary = summary
                existing.analyzed_at = datetime.utcnow()
            else:
                session.add(
                    SkillProfile(
                        id=uuid.uuid4(),
                        user_id=uuid.UUID(user_id),
                        github_username=github_username,
                        skills=skills,
                        repo_count=repo_count,
                        summary=summary,
                        analyzed_at=datetime.utcnow(),
                    )
                )
            await session.commit()

        # ── 5. Update state ────────────────────────────────────────────────
        structured: dict = {
            "skills": skills,
            "summary": summary,
            "repo_count": repo_count,
        }
        return {
            **state,
            "skill_profile": {"skills": skills},
            "structured_output": structured,
            "agent_output": summary,
            "error": None,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("github_analyzer_node failed: %s", exc)
        return {
            **state,
            "agent_output": "Failed to analyse GitHub profile. Please try again later.",
            "error": str(exc),
        }