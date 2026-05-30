"""
Adaptive Interview Agent (DSA + System Design)
===============================================
ORCHESTRATOR INTEGRATION (backend/agents/orchestrator.py):
  Add this import:

    from agents.interview_agent import interview_agent_node

  Register the node:

    graph.add_node("interviewer", interview_agent_node)

  Wire edges as appropriate for your routing logic (e.g., from router → interviewer → END).
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any

from agents.orchestrator import DevBrainState
from services.llm_service import llm

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Static pools
# ─────────────────────────────────────────────────────────────────────────────

_DSA_TOPICS = [
    "arrays", "strings", "linked_lists", "stacks_queues",
    "binary_search", "sorting", "recursion", "dynamic_programming",
    "trees", "graphs", "heaps", "hash_maps", "tries", "sliding_window",
]

_SYSTEM_DESIGN_TOPICS = [
    "distributed cache",
    "URL shortener",
    "news feed (e.g. Twitter/Instagram)",
    "rate limiter",
    "distributed file storage (e.g. Dropbox / Google Drive)",
]

_DIFFICULTY_MAP = {"beginner": "easy", "intermediate": "medium", "advanced": "hard"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_skill_profile(state: DevBrainState) -> dict[str, float]:
    """Return a normalised {topic: score} dict from state or an empty dict."""
    profile: dict = {}
    structured = state.get("structured_output") or {}

    if isinstance(structured, dict):
        profile = structured.get("skill_profile", {})

    if not profile:
        user = state.get("user")
        if user and hasattr(user, "skill_profile") and user.skill_profile:
            raw = getattr(user.skill_profile, "skills", {}) or {}
            for k, v in raw.items():
                if isinstance(v, dict):
                    profile[k] = float(v.get("score", 0.5))
                elif isinstance(v, (int, float)):
                    profile[k] = float(v)

    return profile


def _pick_dsa_topic(skill_profile: dict[str, float]) -> tuple[str, str]:
    """
    Pick a DSA topic where the skill score is in the 0.30-0.65 range
    (areas that need improvement but aren't totally unknown).
    Falls back to a random topic if none match.
    Returns (topic, difficulty).
    """
    candidates = [
        (topic, score)
        for topic, score in skill_profile.items()
        if topic in _DSA_TOPICS and 0.30 <= score <= 0.65
    ]

    if candidates:
        topic, score = random.choice(candidates)
    else:
        topic = random.choice(_DSA_TOPICS)
        score = 0.5

    difficulty = "easy" if score < 0.40 else "medium" if score < 0.60 else "hard"
    return topic, difficulty


def _skill_to_difficulty(skill_profile: dict[str, float]) -> str:
    """Derive an overall skill level from the profile mean score."""
    if not skill_profile:
        return "medium"
    avg = sum(skill_profile.values()) / len(skill_profile)
    if avg < 0.40:
        return "easy"
    if avg < 0.70:
        return "medium"
    return "hard"


def _adjust_difficulty(current: str, next_difficulty: str) -> str:
    order = ["easy", "medium", "hard"]
    idx = order.index(current) if current in order else 1
    if next_difficulty == "harder":
        return order[min(idx + 1, 2)]
    if next_difficulty == "easier":
        return order[max(idx - 1, 0)]
    return current


# ─────────────────────────────────────────────────────────────────────────────
# Core LLM calls
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_opening_question(
    mode: str,
    skill_profile: dict[str, float],
) -> tuple[str, dict[str, Any]]:
    """
    Generate the very first question for the session.
    Returns (user-facing text, metadata dict).
    """
    if mode == "dsa":
        topic, difficulty = _pick_dsa_topic(skill_profile)
        prompt = (
            f"Generate a {difficulty} difficulty DSA coding interview question on the topic: {topic}.\n"
            "Format your response as ONLY a JSON object with these exact fields (do not wrap in markdown):\n"
            "{{\n"
            '  "question": "full problem statement with examples and constraints",\n'
            '  "topic": "the DSA topic",\n'
            '  "difficulty": "easy" | "medium" | "hard",\n'
            '  "hints": ["subtle hint 1", "subtle hint 2"]\n'
            "}}"
        )
        system = (
            "You are an experienced technical interviewer at a top tech company. "
            "Write clear, fair interview questions. Respond ONLY with valid JSON."
        )
    else:
        overall_difficulty = _skill_to_difficulty(skill_profile)
        topic = random.choice(_SYSTEM_DESIGN_TOPICS)
        prompt = (
            f"Generate a system design interview question about: {topic}.\n"
            f"Calibrate for a {overall_difficulty}-level candidate.\n"
            "Format your response as ONLY a JSON object with these exact fields (do not wrap in markdown):\n"
            "{{\n"
            '  "question": "full problem statement with requirements and scope",\n'
            '  "topic": "the system design topic",\n'
            '  "difficulty": "easy" | "medium" | "hard",\n'
            '  "areas_to_cover": ["subsystem 1", "subsystem 2", "subsystem 3", "subsystem 4"]\n'
            "}}"
        )
        system = (
            "You are a staff engineer conducting a system design interview. "
            "Write open-ended, realistic questions. Respond ONLY with valid JSON."
        )

    result: dict = {}
    try:
        result = await llm.structured_call(prompt, system)
    except Exception as exc:
        logger.error("Failed to generate opening question: %s", exc)
        result = {
            "question": f"Explain the core concepts of {topic} and walk me through a practical example.",
            "topic": topic,
            "difficulty": "medium",
            "hints": [],
        }

    question_text = result.get("question", "")
    return question_text, result


async def _evaluate_answer(
    history: list[dict[str, str]],
    original_question: dict[str, Any],
    user_answer: str,
    mode: str,
) -> dict[str, Any]:
    """
    Evaluate the user's last answer.
    Returns evaluation dict with score, feedback, model_answer, next_difficulty.
    """
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in history[:-1]
    )

    prompt = (
        f"You are evaluating a candidate's answer during a {mode} interview.\n\n"
        f"ORIGINAL QUESTION:\n{json.dumps(original_question, indent=2)}\n\n"
        f"CONVERSATION HISTORY:\n{history_text}\n\n"
        f"CANDIDATE'S ANSWER:\n{user_answer}\n\n"
        "Evaluate the answer and return ONLY a JSON object with these exact fields (do not wrap in markdown):\n"
        "{{\n"
        '  "score": 8,\n'
        '  "feedback": "constructive feedback, 3-5 sentences — what was good, what was missing",\n'
        '  "model_answer": "ideal answer or solution outline",\n'
        '  "next_difficulty": "harder",\n'
        '  "key_concepts_missed": ["missed concept 1", "missed concept 2"]\n'
        "}}"
    )
    system = (
        "You are a senior technical interviewer providing fair, educational feedback. "
        "Respond ONLY with valid JSON."
    )

    evaluation: dict = {}
    try:
        evaluation = await llm.structured_call(prompt, system)
    except Exception as exc:
        logger.error("Evaluation call failed: %s", exc)
        evaluation = {
            "score": 5,
            "feedback": "Could not evaluate automatically. Please review your answer.",
            "model_answer": "",
            "next_difficulty": "same",
            "key_concepts_missed": [],
        }

    # Enforce adaptive difficulty based on score
    score = int(evaluation.get("score", 5))
    if score > 7:
        evaluation["next_difficulty"] = "harder"
    elif score < 4:
        evaluation["next_difficulty"] = "easier"

    return evaluation


async def _generate_next_question(
    mode: str,
    current_difficulty: str,
    next_difficulty_adjustment: str,
    used_topics: list[str],
    skill_profile: dict[str, float],
) -> tuple[str, dict[str, Any]]:
    """Generate the follow-up question after an evaluation."""
    new_difficulty = _adjust_difficulty(current_difficulty, next_difficulty_adjustment)

    if mode == "dsa":
        remaining = [t for t in _DSA_TOPICS if t not in used_topics]
        topic = random.choice(remaining) if remaining else random.choice(_DSA_TOPICS)
        prompt = (
            f"Generate a {new_difficulty} DSA interview question on the topic: {topic}.\n"
            f"Previously covered topics (avoid repeating): {', '.join(used_topics)}.\n"
            "Return ONLY a JSON object with these exact fields (do not wrap in markdown):\n"
            "{{\n"
            '  "question": "str",\n'
            '  "topic": "str",\n'
            '  "difficulty": "str",\n'
            '  "hints": ["str", "str"]\n'
            "}}"
        )
        system = (
            "You are a technical interviewer. Generate a fresh coding question. "
            "Respond ONLY with valid JSON."
        )
    else:
        remaining_designs = [t for t in _SYSTEM_DESIGN_TOPICS if t not in used_topics]
        topic = random.choice(remaining_designs) if remaining_designs else random.choice(_SYSTEM_DESIGN_TOPICS)
        prompt = (
            f"Generate a {new_difficulty} system design question about: {topic}.\n"
            f"Previously covered topics (avoid repeating): {', '.join(used_topics)}.\n"
            "Return ONLY a JSON object with these exact fields (do not wrap in markdown):\n"
            "{{\n"
            '  "question": "str",\n'
            '  "topic": "str",\n'
            '  "difficulty": "str",\n'
            '  "areas_to_cover": ["str", "str", "str", "str"]\n'
            "}}"
        )
        system = (
            "You are a staff engineer interviewer. Generate a new system design question. "
            "Respond ONLY with valid JSON."
        )

    result: dict = {}
    try:
        result = await llm.structured_call(prompt, system)
    except Exception as exc:
        logger.error("Next question generation failed: %s", exc)
        result = {
            "question": f"Let's discuss {topic}. Walk me through your approach.",
            "topic": topic,
            "difficulty": new_difficulty,
        }

    return result.get("question", ""), result


async def _generate_session_report(history: list[dict[str, str]], mode: str) -> dict[str, Any]:
    """Generate end-of-session report from full conversation history."""
    history_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content'][:500]}" for msg in history
    )
    prompt = (
        f"This was a {mode} interview session. Here is the full transcript:\n\n"
        f"{history_text}\n\n"
        "Generate a comprehensive final report as ONLY a JSON object with these exact fields (do not wrap in markdown):\n"
        "{{\n"
        '  "overall_score": 8.5,\n'
        '  "strengths": ["str", "str", "str"],\n'
        '  "weak_areas": ["str", "str", "str"],\n'
        '  "recommended_topics": ["str", "str"],\n'
        '  "summary": "str (2-3 sentence overall assessment)",\n'
        '  "interview_readiness": "ready"\n'
        "}}"
    )
    system = (
        "You are a senior hiring manager summarising a candidate's performance. "
        "Be honest, specific, and constructive. Respond ONLY with valid JSON."
    )

    report: dict = {}
    try:
        report = await llm.structured_call(prompt, system)
    except Exception as exc:
        logger.error("Session report generation failed: %s", exc)
        report = {
            "overall_score": 5.0,
            "strengths": ["Attempted all questions"],
            "weak_areas": ["Report generation failed — please review manually"],
            "recommended_topics": [],
            "summary": "Session complete. Report generation encountered an error.",
            "interview_readiness": "almost ready",
        }

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Agent node
# ─────────────────────────────────────────────────────────────────────────────

async def interview_agent_node(state: DevBrainState) -> DevBrainState:
    """
    Adaptive interview agent.

    State contract
    --------------
    Reads:
      state["structured_output"]["mode"]          – "dsa" | "system_design"
      state["conversation_history"]               – list of {role, content}
      state["user_input"]                         – user's latest message (answer)
      state["structured_output"]["skill_profile"] – optional {topic: score}
      state["structured_output"]["current_question"] – metadata for the active question
      state["structured_output"]["used_topics"]       – list of covered topics
      state["structured_output"]["current_difficulty"] – current difficulty string

    Writes:
      state["conversation_history"]
      state["agent_output"]             – response to show the user
      state["structured_output"]        – evaluation + next question (or final report)
    """
    structured: dict = state.get("structured_output") or {}
    mode: str = structured.get("mode", "dsa")
    history: list[dict[str, str]] = state.get("conversation_history") or []
    skill_profile = _get_skill_profile(state)

    response_text: str = ""
    evaluation: dict | None = None
    session_complete = False
    final_report: dict | None = None

    used_topics: list[str] = structured.get("used_topics", [])
    current_question: dict = structured.get("current_question", {})
    current_difficulty: str = structured.get("current_difficulty", "medium")

    # ── Opening question (empty history) ──────────────────────────────────
    if not history:
        question_text, question_meta = await _generate_opening_question(mode, skill_profile)

        used_topics = [question_meta.get("topic", "")]
        current_question = question_meta
        current_difficulty = question_meta.get("difficulty", "medium")

        response_text = question_text
        history = [{"role": "assistant", "content": question_text}]

    else:
        # ── Subsequent turns ──────────────────────────────────────────────
        user_answer: str = state.get("user_input", "")
        if not isinstance(user_answer, str):
            user_answer = json.dumps(user_answer)

        # Append user's message to history
        history.append({"role": "user", "content": user_answer})

        # Check if session is complete (10+ exchanges = 5 Q&A rounds)
        user_turns = sum(1 for m in history if m["role"] == "user")

        if user_turns >= 5:
            # ── End of session ─────────────────────────────────────────
            final_report = await _generate_session_report(history, mode)
            response_text = (
                "That wraps up our session! Here's your performance report:\n\n"
                f"**Overall Score:** {final_report.get('overall_score', 'N/A')}/10\n"
                f"**Readiness:** {final_report.get('interview_readiness', 'N/A')}\n\n"
                f"{final_report.get('summary', '')}"
            )
            history.append({"role": "assistant", "content": response_text})
            session_complete = True

        else:
            # ── Evaluate answer ────────────────────────────────────────
            evaluation = await _evaluate_answer(
                history=history,
                original_question=current_question,
                user_answer=user_answer,
                mode=mode,
            )

            # Generate next question
            next_q_text, next_q_meta = await _generate_next_question(
                mode=mode,
                current_difficulty=current_difficulty,
                next_difficulty_adjustment=evaluation.get("next_difficulty", "same"),
                used_topics=used_topics,
                skill_profile=skill_profile,
            )

            current_question = next_q_meta
            current_difficulty = next_q_meta.get("difficulty", current_difficulty)
            next_topic = next_q_meta.get("topic", "")
            if next_topic and next_topic not in used_topics:
                used_topics.append(next_topic)

            # Build feedback + next question response
            score = evaluation.get("score", 5)
            feedback = evaluation.get("feedback", "")
            missed = evaluation.get("key_concepts_missed", [])
            missed_str = f"\n\n**Key concepts to review:** {', '.join(missed)}" if missed else ""

            response_text = (
                f"**Score: {score}/10**\n\n"
                f"{feedback}"
                f"{missed_str}\n\n"
                "---\n\n"
                f"**Next question ({current_difficulty}):**\n\n{next_q_text}"
            )
            history.append({"role": "assistant", "content": response_text})

    # ── Persist state ──────────────────────────────────────────────────────
    state["conversation_history"] = history
    state["agent_output"] = response_text
    state["structured_output"] = {
        **structured,
        "mode": mode,
        "evaluation": evaluation,
        "current_question": current_question,
        "current_difficulty": current_difficulty,
        "used_topics": used_topics,
        "session_complete": session_complete,
        "final_report": final_report,
        "skill_profile": skill_profile,
    }

    logger.info(
        "interview_agent_node complete — mode=%s turns=%d complete=%s",
        mode,
        len(history),
        session_complete,
    )
    return state