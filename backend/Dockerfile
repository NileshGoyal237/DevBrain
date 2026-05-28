FROM python:3.11-slim

# ── Labels ──────────────────────────────────────────────────────────────────
LABEL org.opencontainers.image.title="DevBrain Backend"
LABEL org.opencontainers.image.description="FastAPI + LangGraph AI backend for DevBrain"
LABEL org.opencontainers.image.source="https://github.com/your-org/devbrain"

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (layer-cached) ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# ── Persistent ChromaDB volume mount point ───────────────────────────────────
RUN mkdir -p /app/data/chroma

# ── Non-root user for security ───────────────────────────────────────────────
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN chown -R appuser:appgroup /app
USER appuser

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--http", "httptools"]