# Build ONLY a generated allowlisted context from export_dataset.py --build-context.
FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
COPY requirements.lock /tmp/requirements.lock
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && pip install --no-cache-dir -r /tmp/requirements.lock \
    && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY arena /app/arena
COPY openenv.yaml /app/openenv.yaml
COPY NOTICE.md /app/NOTICE.md
COPY LICENSE-ARENA.md /app/LICENSE-ARENA.md
COPY licenses /app/licenses
RUN useradd --uid 10001 --create-home runner && chmod -R a-w /app
USER 10001
ENV PYTHONUNBUFFERED=1 ENABLE_WEB_INTERFACE=false SAGACE_REQUIRE_SELECTION=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)"
CMD ["python", "-m", "arena.app"]
