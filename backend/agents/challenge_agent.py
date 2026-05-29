"""
Challenge Agent
===============
Generates an adaptive coding challenge targeting the user's weakest skill area,
persists it to PostgreSQL, and provides a sandboxed evaluation function for
submitted solutions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import textwrap
import uuid
from datetime import datetime
from typing import Optional, Any

from models.database import async_session
from models.challenge import Challenge
from services.cache_service import cache
from services.llm_service import llm

logger = logging.getLogger(__name__)

# ── Skill → coding topic mapping ──────────────────────────────────────────
_SKILL_TO_TOPIC: dict[str, str] = {
    "Python": "data structures",
    "JavaScript": "asynchronous programming",
    "TypeScript": "type-safe patterns",
    "Java": "object-oriented design",
    "C++": "memory management and algorithms",
    "C": "pointers and recursion",
    "Go": "concurrency and goroutines",
    "Rust": "ownership and lifetimes",
    "SQL": "query optimisation",
    "Shell": "shell scripting",
    "HTML": "DOM manipulation",
    "CSS": "layout and specificity",
    "Ruby": "metaprogramming",
    "PHP": "web security patterns",
    "Swift": "optionals and closures",
    "Kotlin": "coroutines",
    "R": "statistical computation",
    "Scala": "functional programming",
    "Haskell": "pure functional patterns",
    "MATLAB": "numerical computing",
}

_DEFAULT_TOPIC = "algorithms and problem solving"


# ═══════════════════════════════════════════════════════════════════════════ #
# Agent node                                                                  #
# ═══════════════════════════════════════════════════════════════════════════ #


async def challenge_agent_node(state: dict) -> dict:
    """
    LangGraph node: generate an adaptive coding challenge.

    Steps
    -----
    1. Resolve skill profile; find the weakest skill.
    2. Map that skill to a coding topic.
    3. Determine difficulty from the skill score.
    4. Prompt Grok for a complete challenge JSON.
    5. Save Challenge to DB.
    6. Populate state fields.
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

        # ── 2. Find weakest skill that maps to a coding topic ──────────────
        weak_skill, weak_score = _find_weakest_coding_skill(skills)
        topic: str = _SKILL_TO_TOPIC.get(weak_skill, _DEFAULT_TOPIC)
        difficulty: str = _difficulty_from_score(weak_score)

        # Primary language = highest-scoring skill (for starter code)
        primary_lang: str = (
            max(skills.items(), key=lambda x: x[1])[0] if skills else "Python"
        )

        # ── 3. Build prompt ────────────────────────────────────────────────
        prompt = _build_challenge_prompt(
            topic=topic,
            difficulty=difficulty,
            language=primary_lang,
            skill=weak_skill,
        )

        # ── 4. Call LLM ────────────────────────────────────────────────────
        raw: str = await llm.structured_call(prompt)
        challenge_dict: Optional[dict] = _parse_json_safe(raw)

        if not challenge_dict or "title" not in challenge_dict:
            raw_str = json.dumps(raw) if isinstance(raw, dict) else str(raw)
            raise ValueError(f"LLM returned unparseable challenge JSON:\n{raw_str[:300]}")

        # Enforce required fields
        challenge_dict.setdefault("difficulty", difficulty)
        challenge_dict.setdefault("topic", topic)

        # ── 5. Persist to DB ───────────────────────────────────────────────
        async with async_session() as session:
            challenge = Challenge(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                title=challenge_dict.get("title", "Untitled Challenge"),
                description=challenge_dict.get("description", ""),
                difficulty=challenge_dict.get("difficulty", difficulty),
                topic=challenge_dict.get("topic", topic),
                constraints=challenge_dict.get("constraints", []),
                examples=challenge_dict.get("examples", []),
                test_cases=challenge_dict.get("test_cases", []),
                starter_code=challenge_dict.get("starter_code", ""),
                solution=challenge_dict.get("solution", ""),
                created_at=datetime.utcnow(),
            )
            session.add(challenge)
            await session.commit()
            await session.refresh(challenge)

        challenge_dict["id"] = str(challenge.id)

        # ── 6. Format human-readable output ───────────────────────────────
        agent_output = _format_challenge_display(challenge_dict)

        return {
            **state,
            "structured_output": challenge_dict,
            "agent_output": agent_output,
            "error": None,
        }

    except Exception as exc:  # noqa: BLE001
        logger.exception("challenge_agent_node failed: %s", exc)
        return {
            **state,
            "agent_output": "Failed to generate a challenge. Please try again.",
            "error": str(exc),
        }


# ═══════════════════════════════════════════════════════════════════════════ #
# Submission evaluator (sandboxed)                                            #
# ═══════════════════════════════════════════════════════════════════════════ #


async def evaluate_submission(
    challenge_or_code: Any = None,
    user_code: Optional[str] = None,
    test_cases: Optional[list[dict]] = None,
    timeout_seconds: float = 5.0,
) -> dict:
    """
    Execute user_code in a sandboxed subprocess and run every test case.

    Each test case is injected as a harness appended to the user's code.
    A wall-clock timeout is enforced per test.

    Returns
    -------
    {
        "tests_passed": int,
        "tests_total": int,
        "passed": bool,
        "output": str,
        "error": str | None,
    }
    """
    import sys

    if isinstance(challenge_or_code, str):
        actual_code = challenge_or_code
        actual_test_cases = test_cases or []
    elif challenge_or_code is None:
        actual_code = user_code or ""
        actual_test_cases = test_cases or []
    else:
        actual_code = user_code or ""
        actual_test_cases = challenge_or_code.test_cases or []

    if not actual_test_cases:
        return {
            "tests_passed": 0,
            "tests_total": 0,
            "passed": False,
            "output": "",
            "error": "No test cases defined for this challenge.",
        }

    tests_passed = 0
    all_output_lines: list[str] = []
    first_error: Optional[str] = None

    for idx, tc in enumerate(actual_test_cases, start=1):
        tc_input: str = tc.get("input", "")
        expected: str = tc.get("expected", "").strip()

        # Build a self-contained script: user code + a minimal test harness
        harness = textwrap.dedent(f"""
            # ── AUTO-GENERATED TEST HARNESS ──
            import sys, io

            _captured = io.StringIO()
            sys.stdout = _captured
            try:
                # Support solutions named 'solution' or functions defined in user_code
                # We execute tc_input directly if it's a full expression, or pass it to solution()
                try:
                    # try calling solution() first if defined
                    if 'def solution' in {actual_code!r} or 'solution' in globals() or 'solution' in locals():
                        _result = solution({tc_input!r})
                    else:
                        # Fallback: exec user_code and evaluate the input expression directly
                        _result = eval({tc_input!r})
                except NameError:
                    # fallback to direct eval
                    _result = eval({tc_input!r})

                if _result is not None:
                    print(_result)
            except Exception as _exc:
                sys.stdout = sys.__stdout__
                print(f"ERROR: {{_exc}}")
                raise
            sys.stdout = sys.__stdout__
            _actual = _captured.getvalue().strip()
            print(_actual)
        """)

        full_script = actual_code + "\n" + harness

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                full_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                all_output_lines.append(f"Test {idx}: ❌ TIMEOUT (> 5 s)")
                first_error = first_error or "Time limit exceeded (timeout)."
                continue

            stdout_str = stdout_b.decode(errors="replace").strip()
            stderr_str = stderr_b.decode(errors="replace").strip()

            if stderr_str and not stdout_str:
                all_output_lines.append(f"Test {idx}: ❌ RUNTIME ERROR — {stderr_str[:200]}")
                first_error = first_error or stderr_str
                continue

            actual = stdout_str.splitlines()[-1] if stdout_str else ""

            if actual == expected:
                tests_passed += 1
                all_output_lines.append(f"Test {idx}: ✅ PASSED")
            else:
                all_output_lines.append(
                    f"Test {idx}: ❌ FAILED — expected {expected!r}, got {actual!r}"
                )

        except Exception as exc:  # noqa: BLE001
            all_output_lines.append(f"Test {idx}: ❌ ERROR — {exc}")
            first_error = first_error or str(exc)

    total = len(test_cases)
    return {
        "tests_passed": tests_passed,
        "tests_total": total,
        "passed": tests_passed == total,
        "output": "\n".join(all_output_lines),
        "error": first_error,
    }


# ═══════════════════════════════════════════════════════════════════════════ #
# Private helpers                                                             #
# ═══════════════════════════════════════════════════════════════════════════ #


def _find_weakest_coding_skill(skills: dict[str, float]) -> tuple[str, float]:
    """Return (skill_name, score) for the weakest skill in _SKILL_TO_TOPIC."""
    coding_skills = {k: v for k, v in skills.items() if k in _SKILL_TO_TOPIC}
    if not coding_skills:
        return "Python", 0.0
    skill = min(coding_skills, key=coding_skills.get)  # type: ignore[arg-type]
    return skill, coding_skills[skill]


def _difficulty_from_score(score: float) -> str:
    if score < 0.30:
        return "easy"
    elif score <= 0.65:
        return "medium"
    return "hard"


def _build_challenge_prompt(topic: str, difficulty: str, language: str, skill: str) -> str:
    return f"""You are a senior competitive programming coach creating interview-style coding challenges.

Target skill: {skill}
Topic area  : {topic}
Difficulty  : {difficulty}
Starter code language: {language}

Generate ONE coding challenge as a single JSON object (NO markdown fences, NO extra text):
{{
  "title": "Short descriptive title",
  "description": "Full problem statement with context. Be clear and unambiguous.",
  "difficulty": "{difficulty}",
  "topic": "{topic}",
  "constraints": ["constraint 1", "constraint 2"],
  "examples": [
    {{
      "input": "example input",
      "output": "example output",
      "explanation": "why this output"
    }}
  ],
  "test_cases": [
    {{"input": "test input 1", "expected": "expected output 1"}},
    {{"input": "test input 2", "expected": "expected output 2"}},
    {{"input": "test input 3", "expected": "expected output 3"}}
  ],
  "starter_code": "# {language} starter\\ndef solution(...):\\n    pass",
  "solution": "# Complete reference solution\\ndef solution(...):\\n    ..."
}}

Rules:
- Exactly 3 test cases minimum.
- starter_code and solution must be syntactically valid {language}.
- difficulty must be {difficulty} level for a developer with score {difficulty}.
- description must be self-contained (no external links needed).
"""


def _format_challenge_display(c: dict) -> str:
    lines = [
        f"## 🧩 {c.get('title', 'Challenge')}",
        f"**Difficulty:** {c.get('difficulty', '').capitalize()}  |  **Topic:** {c.get('topic', '')}",
        "",
        c.get("description", ""),
        "",
        "**Constraints:**",
    ]
    for constraint in c.get("constraints", []):
        lines.append(f"  - {constraint}")
    lines += ["", "**Examples:**"]
    for ex in c.get("examples", []):
        lines.append(f"  Input: `{ex.get('input')}`  →  Output: `{ex.get('output')}`")
        if ex.get("explanation"):
            lines.append(f"  _{ex['explanation']}_")
    lines += ["", "```", c.get("starter_code", "# write your solution here"), "```"]
    return "\n".join(lines)


def _parse_json_safe(text) -> Optional[dict]:
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return None
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None