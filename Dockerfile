# Voice Live Gradio — container image for Azure Container Apps
#
# Build context is the repo root. Image runs `python app.py`, which
# dispatches into the demo shells (MODE=demo by default).
FROM python:3.13-slim

# System packages needed by FastRTC / PyAV (ffmpeg) and a couple of
# native libs Gradio likes to have around. Keep this list minimal.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official standalone image (smaller than pip install uv).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Resolve dependencies first so layer caching survives source edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application source.
COPY . .

# Finalise the venv now that the project itself is present.
RUN uv sync --frozen --no-dev

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    PORT=7860 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

EXPOSE 7860

CMD ["uv", "run", "--no-dev", "python", "app.py"]
