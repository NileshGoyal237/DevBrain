"""
backend/main.py
DevBrain API — FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.auth import router as auth_router
from api.routes.github import router as github_router
from api.routes.roadmap import router as roadmap_router
from api.routes.challenges import router as challenges_router
from api.routes.review import router as review_router
from api.routes.interview import router as interview_router
from api.routes.resources import router as resources_router
from api.routes.progress import router as progress_router
from core.config import settings
from models.database import Base, engine


# ── Application lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


# ── Application factory ───────────────────────────────────────────────────────

app = FastAPI(
    title="DevBrain API",
    version="1.0.0",
    description=(
        "AI-powered developer growth platform. "
        "Analyses your GitHub repos, builds a skill profile, and drives "
        "personalised learning via roadmaps, challenges, code review, and mock interviews."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router,       prefix="/auth")
app.include_router(github_router,     prefix="/github")
app.include_router(roadmap_router,    prefix="/roadmap")
app.include_router(challenges_router, prefix="/challenges")
app.include_router(review_router,     prefix="/review")
app.include_router(interview_router,  prefix="/interview")
app.include_router(resources_router,  prefix="/resources")
app.include_router(progress_router,   prefix="/progress")


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"], summary="Service health check")
async def health():
    return {"status": "ok", "model": settings.GROK_MODEL}