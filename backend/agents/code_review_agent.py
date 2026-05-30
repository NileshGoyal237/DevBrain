"""
Code Review Agent with Self-Reflection Loop
============================================
ORCHESTRATOR INTEGRATION (backend/agents/orchestrator.py):
  Replace stub nodes with these imports at the top of orchestrator.py:

    from agents.code_review_agent import code_review_node, reflection_node, should_reflect_again

  Then replace stub node registrations with:

    graph.add_node("code_reviewer", code_review_node)
    graph.add_node("reflector", reflection_node)
    graph.add_conditional_edges(
        "reflector",
        should_reflect_again,
        {"review_again": "code_reviewer", "done": END}
    )
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.orchestrator import DevBrainState
from services.llm_service import llm
from services.vector_store import vector_store

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Prompt constants
# ─────────────────────────────────────────────────────────────────────────────

REVIEW_SYSTEM = (
    "You are a senior software engineer with 10+ years experience doing code reviews. "
    "Be specific, actionable, and educational. Always include Big-O complexity."
)

REVIEW_PROMPT = (
    "Review this {language} code:\n"
    "```{language}\n{code}\n```\n"
    "{context_block}"
    "Return ONLY a JSON object with these exact fields (do not wrap in markdown lists):\n"
    "{{\n"
    '  "score": 8,\n'
    '  "annotations": [ {{"line": 42, "issue": "missing type hint", "fix": "add -> int"}} ],\n'
    '  "complexity": {{"time": "O(N)", "space": "O(1)"}},\n'
    '  "edge_cases": [ "empty list input" ],\n'
    '  "improvements": [ {{"title": "Use list comprehension", "description": "Faster", "code_example": "x = [1]"}} ],\n'
    '  "best_practices": [ "PEP8 violation" ],\n'
    '  "summary": "overall assessment"\n'
    "}}"
)

REFLECTION_SYSTEM = "You are a code review quality auditor."

REFLECTION_PROMPT = (
    "A senior engineer reviewed code and produced this feedback:\n"
    "{review_json}\n\n"
    "Evaluate the quality of this review (0.0-1.0) based on:\n"
    "1. Are annotations specific (not generic like 'add comments')?\n"
    "2. Does complexity include both time AND space Big-O?\n"
    "3. Are there >= 2 concrete improvements with code examples?\n"
    "4. Are edge cases actually relevant to the code?\n"
    "5. Is the score justified by the feedback?\n"
    'Return ONLY JSON: {{"quality_score": float, "critique": str, "missing": list[str]}}'
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_context_block(similar_reviews: list[dict[str, Any]]) -> str:
    """Format top-2 similar past reviews as additional context."""
    if not similar_reviews:
        return ""

    top = similar_reviews[:2]
    lines = ["Here are two similar past reviews for context:\n"]
    for i, rev in enumerate(top, 1):
        summary = rev.get("summary", "")
        score = rev.get("score", "N/A")
        language = rev.get("language", "unknown")
        lines.append(
            f"Past review {i} ({language}, score {score}/10): {summary}\n"
        )
    lines.append("\nUse these as reference but review the new code independently.\n\n")
    return "".join(lines)


def _extract_language_and_code(state: DevBrainState) -> tuple[str, str]:
    """Pull language + code out of state, preferring structured_output over raw input."""
    structured: dict = state.get("structured_output") or {}
    language = structured.get("language") or "python"
    code = structured.get("code") or ""

    if not code:
        # Fallback: try to parse from user_input (plain string or JSON blob)
        user_input = state.get("user_input", "")
        if isinstance(user_input, str):
            try:
                parsed = json.loads(user_input)
                language = parsed.get("language", language)
                code = parsed.get("code", "")
            except (json.JSONDecodeError, TypeError):
                code = user_input  # treat raw text as the code itself

    return language, code


# ─────────────────────────────────────────────────────────────────────────────
# Agent nodes
# ─────────────────────────────────────────────────────────────────────────────

async def code_review_node(state: DevBrainState) -> DevBrainState:
    """
    Primary review node.

    1. Fetches similar past reviews from ChromaDB for few-shot context.
    2. Builds the review prompt and calls Grok.
    3. Parses the JSON response and persists it in state.
    """
    language, code = _extract_language_and_code(state)

    # ── Step 1: retrieve similar past reviews ──────────────────────────────
    similar_reviews: list[dict] = []
    try:
        similar_reviews = await vector_store.search_similar_reviews(code, language)
    except Exception as exc:
        logger.warning("Vector store lookup failed (non-fatal): %s", exc)

    context_block = _build_context_block(similar_reviews)

    # ── Step 2: build prompt ───────────────────────────────────────────────
    # Append any prior reflection critique that was injected into user_input
    extra_context = ""
    user_input = state.get("user_input", "")
    if isinstance(user_input, str) and "Previous review critique:" in user_input:
        critique_start = user_input.index("Previous review critique:")
        extra_context = "\n\nIMPORTANT FEEDBACK FROM AUDITOR:\n" + user_input[critique_start:]

    prompt = REVIEW_PROMPT.format(
        language=language,
        code=code,
        context_block=context_block,
    ) + extra_context

    # ── Step 3: call LLM ───────────────────────────────────────────────────
    review_dict: dict = {}
    try:
        review_dict = await llm.structured_call(prompt, REVIEW_SYSTEM)
    except Exception as exc:
        logger.error("LLM call failed in code_review_node: %s", exc)
        review_dict = {
            "score": 0,
            "annotations": [],
            "complexity": {"time": "unknown", "space": "unknown"},
            "edge_cases": [],
            "improvements": [],
            "best_practices": [],
            "summary": f"Review failed due to LLM error: {exc}",
        }

    # Ensure required keys exist (defensive defaults)
    review_dict.setdefault("score", 5)
    review_dict.setdefault("annotations", [])
    review_dict.setdefault("complexity", {"time": "O(?)", "space": "O(?)"})
    review_dict.setdefault("edge_cases", [])
    review_dict.setdefault("improvements", [])
    review_dict.setdefault("best_practices", [])
    review_dict.setdefault("summary", "")

    # Carry language and code forward so downstream nodes / routes can use them
    review_dict["language"] = language
    review_dict["code"] = code

    # ── Step 4: update state ───────────────────────────────────────────────
    state["structured_output"] = review_dict
    state["agent_output"] = json.dumps(review_dict)
    state["iteration_count"] = state.get("iteration_count", 0) + 1

    logger.info(
        "code_review_node complete — score=%s iteration=%s",
        review_dict.get("score"),
        state["iteration_count"],
    )
    return state


async def reflection_node(state: DevBrainState) -> DevBrainState:
    """
    Reflection / quality-audit node.

    Evaluates the review produced by code_review_node.
    If quality_score < 0.75, injects the critique back into user_input so
    code_review_node can improve on the next iteration.
    """
    review_json = state.get("agent_output", "{}")

    reflection_dict: dict = {}
    try:
        prompt = REFLECTION_PROMPT.format(review_json=review_json)
        reflection_dict = await llm.structured_call(prompt, REFLECTION_SYSTEM)
    except Exception as exc:
        logger.error("LLM call failed in reflection_node: %s", exc)
        reflection_dict = {
            "quality_score": 1.0,   # pass-through on error to avoid infinite loop
            "critique": f"Reflection failed: {exc}",
            "missing": [],
        }

    reflection_dict.setdefault("quality_score", 1.0)
    reflection_dict.setdefault("critique", "")
    reflection_dict.setdefault("missing", [])

    quality_score: float = float(reflection_dict["quality_score"])
    state["reflection_score"] = quality_score

    logger.info(
        "reflection_node — quality_score=%.2f iteration=%s",
        quality_score,
        state.get("iteration_count", 0),
    )

    if quality_score < 0.75:
        critique = reflection_dict["critique"]
        missing = reflection_dict["missing"]
        missing_str = ", ".join(missing) if missing else "none specified"

        base_input = state.get("user_input", "")
        # Strip any prior critique appendage to avoid duplication
        if "Previous review critique:" in base_input:
            base_input = base_input[: base_input.index("Previous review critique:")].rstrip()

        state["user_input"] = (
            f"{base_input}\n\n"
            f"Previous review critique: {critique}. "
            f"Missing: {missing_str}. "
            "Please improve these specific areas."
        )
        logger.info("Quality below threshold (%.2f < 0.75) — requesting re-review.", quality_score)

    return state


# ─────────────────────────────────────────────────────────────────────────────
# Conditional edge
# ─────────────────────────────────────────────────────────────────────────────

def should_reflect_again(state: DevBrainState) -> str:
    """
    LangGraph conditional edge after reflection_node.

    Returns 'review_again' if the reflection score is below threshold AND
    we haven't hit the iteration cap; otherwise returns 'done'.
    """
    reflection_score: float = float(state.get("reflection_score", 1.0))
    iteration_count: int = int(state.get("iteration_count", 0))
    max_iterations: int = int(state.get("max_iterations", 3))

    if reflection_score < 0.75 and iteration_count < max_iterations:
        logger.info(
            "should_reflect_again → review_again (score=%.2f, iter=%d/%d)",
            reflection_score,
            iteration_count,
            max_iterations,
        )
        return "review_again"

    logger.info(
        "should_reflect_again → done (score=%.2f, iter=%d/%d)",
        reflection_score,
        iteration_count,
        max_iterations,
    )
    return "done"