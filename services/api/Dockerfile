FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROJECT_ROOT=/app \
    HF_HOME=/app/data/hf-cache \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Native libraries required by docling's vision stack (opencv/pillow backends).
# libgl/libglib: docling vision stack; antiword/catdoc: legacy .doc text;
# libarchive-tools (bsdtar) + unar: archive extraction in the batch corpus
# ingester. unar handles multi-volume RAR (.partN.rar) correctly, which
# libarchive/bsdtar silently truncates.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxcb1 libxext6 libsm6 \
    antiword catdoc libarchive-tools unar \
    && rm -rf /var/lib/apt/lists/*

# Dependency layer: locked resolve without the project so code edits reuse the cache.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra ingest

COPY README.md ./
COPY src ./src
COPY services ./services
COPY eval ./eval
COPY scripts ./scripts

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra ingest

EXPOSE 8000

CMD ["fastapi", "run", "services/api/main.py", "--host", "0.0.0.0", "--port", "8000"]
