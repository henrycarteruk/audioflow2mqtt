# Pinned Python base image
FROM python:3.12-slim

# Install tzdata so a TZ environment variable (e.g. TZ=America/Chicago) resolves
# named time zones for log timestamps. The slim base image omits tzdata, which
# would otherwise leave logs in UTC regardless of TZ. Early layer: rarely changes.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# Pinned uv binary from the official image (build-time dependency manager only)
COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/uv

# Compile bytecode for faster startup, copy from the cache mount instead of
# hardlinking, use the base image's Python (don't download one), and put the
# venv on PATH so the app runs without invoking uv at startup.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PATH="/.venv/bin:$PATH"

# Run from / so a config.yaml mounted at /config.yaml is found (see README)
WORKDIR /

# Install locked runtime dependencies into /.venv. The manifests are bind-mounted
# (so they add no image layer) and uv's download cache is reused across builds;
# this layer is only rebuilt when pyproject.toml or uv.lock change.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv sync --frozen --no-dev --no-install-project

COPY audioflow2mqtt/ ./audioflow2mqtt/

# Health-check endpoint (default port; override with HEALTH_CHECK_PORT at runtime)
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]

# Run directly from the venv python (no uv resolution at container startup)
CMD ["python", "-m", "audioflow2mqtt"]
