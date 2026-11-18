# syntax=docker/dockerfile:1.7
# Shared image for API and worker. Worker needs tesseract (local OCR, ADR-0005).
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-eng libgl1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/src apps/api/src
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY apps/worker/src apps/worker/src
RUN uv sync --frozen --no-dev

FROM base AS runtime
RUN useradd --system --uid 10001 --home /app compback
COPY --from=deps /app /app
COPY alembic.ini ./
COPY migrations ./migrations
ENV PATH="/app/.venv/bin:$PATH"
USER 10001
EXPOSE 8000
CMD ["uvicorn", "compback_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
