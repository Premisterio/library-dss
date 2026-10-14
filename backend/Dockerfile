# syntax=docker/dockerfile:1
# Build context: repository root (the uv workspace lockfile lives there).
ARG PYTHON_VERSION=3.15

FROM ghcr.io/astral-sh/uv:0.13 AS uv

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /srv
# Workspace manifests first: dependency layers stay cached until the lockfile changes.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/
COPY generator/pyproject.toml generator/

# Dev: every workspace package with dev groups; compose bind-mounts backend/ for --reload.
FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-packages --no-install-workspace
COPY backend backend
COPY generator generator
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --all-packages
WORKDIR /srv/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# Prod: backend runtime dependencies only, unprivileged user.
FROM base AS prod
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package library-dss-backend --no-dev --no-install-workspace
COPY backend backend
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --package library-dss-backend --no-dev \
 && useradd --system --uid 10001 --no-create-home app
USER app
WORKDIR /srv/backend
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"]
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
