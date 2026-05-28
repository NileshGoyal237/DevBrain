"""
backend/models/interview.py
Mock technical interview sessions — DSA and system design modes.
"""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from models.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    # ── Primary key ──────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Interview mode ────────────────────────────────────────────────────────
    # "dsa" | "system_design"
    mode: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── Conversation history ──────────────────────────────────────────────────
    # Ordered list of turn dicts:
    # [
    #   {"role": "assistant", "content": "Let's start. Given an array..."},
    #   {"role": "user",      "content": "I would use a hash map..."},
    #   ...
    # ]
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # ── Scoring (set when session ends) ──────────────────────────────────────
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Topics actually covered during the session ────────────────────────────
    # Example: ["Binary Search", "Recursion", "Time Complexity"]
    topics_covered: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="interview_sessions",
    )

    def __repr__(self) -> str:
        return (
            f"<InterviewSession id={self.id} mode={self.mode} "
            f"turns={len(self.messages) if self.messages else 0}>"
        )