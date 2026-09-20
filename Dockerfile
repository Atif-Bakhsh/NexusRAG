FROM python:3.12.9-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable
COPY alembic.ini ./
COPY migrations ./migrations
COPY corpus ./corpus
COPY evaluation ./evaluation
COPY docs ./docs
RUN mkdir -p artifacts results .cache
EXPOSE 8000 8501
