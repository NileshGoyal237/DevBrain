"""
Roadmap Agent
=============
Generates a personalised 6-week learning roadmap tailored to the user's
current skill profile and target role, then persists it to PostgreSQL.

Rules enforced in the prompt:
- Skip any topic where the user's skill score > 0.7.
- Prioritise DSA for SDE/Backend roles; ML pipelines for ML roles;
  React/Node for Full-Stack; IaC/containers for DevOps.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update

from models.database import async_session
from models.roadmap import Roadmap
from services.cache_service import cache
from services.llm_service import llm

logger = logging.getLogger(__name__)

# ── Role → priority topics hint ───────────────────────────────────────────
_ROLE_HINTS: dict[str, str] = {
    "SDE Intern": "algorithms, data structures, system design basics, OOP",
    "Backend": "system design, databases, REST APIs, caching, message queues",
    "ML": "ML pipelines, model evaluation, feature engineering, statistics, deep learning",
    "Full-Stack": "React, Node.js, REST/GraphQL, databases, deployment",
    "DevOps": "CI/CD, Kubernetes, Docker, IaC (Terraform), cloud services, monitoring",
}


async def roadmap_agent_node(state: dict) -> dict:
    """
    LangGraph node: build a structured 6-week learning roadmap.

    Steps
    -----
    1. Resolve skill profile from state or Redis cache.
    2. Build a detailed prompt instructing Grok to output JSON.
    3. Parse the JSON response (strict; fall back to regex extraction).
    4. Deactivate previous active roadmap for this user.
    5. Persist the new Roadmap to PostgreSQL.
    6. Populate state["structured_output"] and state["agent_output"].
    """
    user_id: str = state["user_id"]

    try:
        # ── 1. Resolve skill profile ───────────────────────────────────────
        skill_profile: dict = state.get("skill_profile") or {}
        skills: dict[str, float] = skill_profile.get("skills", {})

        if not skills:
            cached = await cache.get_skill_profile(user_id)
            if cached:
                skills = cached.get("skills", {})

        structured_out = state.get("structured_output") or {}
        target_role: str = (
            structured_out.get("target_role")
            or "SDE Intern"
        )
        role_hint: str = _ROLE_HINTS.get(target_role, _ROLE_HINTS["SDE Intern"])

        # Build a readable skill snapshot, omitting mastered topics (>0.7)
        weak_skills = {k: v for k, v in skills.items() if v <= 0.7}
        skill_summary = "\n".join(
            f"  {lang}: {score:.2f}"
            for lang, score in sorted(weak_skills.items(), key=lambda x: x[1])
        ) or "  No weak skills detected — challenge them with advanced topics."

        mastered = [k for k, v in skills.items() if v > 0.7]
        mastered_str = ", ".join(mastered) if mastered else "none"

        # ── 2. Build prompt ────────────────────────────────────────────────
        prompt = f"""You are an expert software-engineering curriculum designer.

Target role : {target_role}
Role priorities: {role_hint}

Developer's WEAK skill scores (0 = novice, 1 = expert):
{skill_summary}

Already mastered (score > 0.70 — DO NOT assign these as primary topics): {mastered_str}

Design a personalised 6-week learning roadmap. Rules:
- EXACTLY 6 week objects.
- DO NOT assign a "focus" topic where the developer already has score > 0.70.
- Prioritise the role-specific skills listed above.
- Each week has 3-5 specific subtopics.
- Give a concrete reason why this week's focus was chosen.
- Increase difficulty progressively.

Return ONLY valid JSON (no markdown fences, no extra text) in this exact schema:
{{
  "target_role": "{target_role}",
  "weeks": [
    {{
      "week": 1,
      "focus": "Topic Name",
      "topics": ["subtopic1", "subtopic2", "subtopic3"],
      "reason": "Why this week focuses on this topic given the developer's profile."
    }}
  ]
}}"""

        # ── 3. Call LLM and parse ──────────────────────────────────────────
        raw_response: str = await llm.structured_call(prompt)
        roadmap_json: Optional[dict] = _parse_json_safe(raw_response)

        if not roadmap_json or "weeks" not in roadmap_json:
            raise ValueError(f"LLM returned unparseable roadmap JSON: {raw_response[:300]}")

        # Enforce exactly 6 weeks (trim or pad)
        weeks = roadmap_json["weeks"][:6]
        if len(weeks) < 6:
            logger.warning("LLM returned only %d weeks — padding to 6.", len(weeks))
            for i in range(len(weeks) + 1, 7):
                weeks.append(
                    {
                        "week": i,
                        "focus": "Advanced Practice & Review",
                        "topics": ["LeetCode hard problems", "mock interview prep", "system design"],
                        "reason": "Consolidate learning and prepare for interviews.",
                    }
                )
        roadmap_json["weeks"] = weeks

        # ── 4. Deactivate previous active roadmap ─────────────────────────
        async with async_session() as session:
            await session.execute(
                update(Roadmap)
                .where(
                    Roadmap.user_id == uuid.UUID(user_id),
                    Roadmap.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )

            # ── 5. Persist new roadmap ─────────────────────────────────────
            new_roadmap = Roadmap(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                target_role=target_role,
                plan=roadmap_json,
                is_active=True,
                created_at=datetime.utcnow(),
            )
            session.add(new_roadmap)
            await session.commit()
            await session.refresh(new_roadmap)

        # ── 6. Human-readable summary ──────────────────────────────────────
        lines = [f"📅 Your personalised 6-week roadmap for **{target_role}**:\n"]
        for w in roadmap_json["weeks"]:
            topics_str = ", ".join(w.get("topics", []))
            lines.append(f"  Week {w['week']}: **{w['focus']}** — {topics_str}")
        human_summary = "\n".join(lines)

        return {
            **state,
            "structured_output": roadmap_json,
            "agent_output": human_summary,
            "error": None,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("roadmap_agent_node failed: %s", exc)
        return {
            **state,
            "agent_output": "Failed to generate roadmap. Please ensure your GitHub profile has been analysed first.",
            "error": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────── #
# Helpers                                                                     #
# ─────────────────────────────────────────────────────────────────────────── #


def _parse_json_safe(text) -> Optional[dict]:
    """
    Attempt JSON parsing; also handles responses wrapped in markdown fences.
    """
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return None
    text = text.strip()
    # Strip possible ```json ... ``` wrapper
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: find first { ... } block
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None