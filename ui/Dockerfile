FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first so code changes don't bust the layer cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

RUN useradd --create-home app
USER app

EXPOSE 8711
# A host (e.g. Render) may inject PORT; default to 8711 for docker compose.
CMD ["sh", "-c", "exec streamlit run app.py --server.address 0.0.0.0 --server.port ${PORT:-8711}"]
