# This opt-in target lets tests inspect the actual filtered build context.
FROM scratch AS build-context
COPY . /

FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.8@sha256:3b7b60a81d3c57ef471703e5c83fd4aaa33abcd403596fb22ab07db85ae91347 /uv /bin/uv
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never uv sync --locked --no-dev --no-editable

FROM base AS runtime
COPY --from=builder /app/.venv /app/.venv
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=4s --start-period=10s --retries=3 \
    CMD ["python", "-m", "may_mcp.healthcheck"]
ENTRYPOINT ["python", "-m", "may_mcp"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
