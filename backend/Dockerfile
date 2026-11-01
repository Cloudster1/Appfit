FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/models

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra ml --no-install-project

COPY alembic.ini entrypoint.sh ./
COPY alembic ./alembic
COPY src ./src
COPY eval ./eval
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra ml \
    && chmod +x entrypoint.sh \
    && useradd --create-home --uid 10001 appfit \
    && mkdir -p /models && chown appfit /models

USER appfit
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "appfit.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
