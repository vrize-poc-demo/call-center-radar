FROM node:20-bookworm-slim AS web-build

WORKDIR /app

COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci

COPY apps/web apps/web
RUN npm run build --workspace=@call-center-radar/web


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CALL_RADAR_DATABASE_PATH=/app/data/call_radar.db
ENV CALL_RADAR_UPLOAD_DIR=/app/data/uploads
ENV CALL_RADAR_STATIC_DIR=/app/apps/web/dist
ENV CALL_RADAR_SAMPLE_DATA_DIR=/app/sample-data/callradar-data
ENV CALL_RADAR_OLLAMA_BASE_URL=http://ollama:11434
ENV CALL_RADAR_PROCESSING_WORKER_ENABLED=true

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api apps/api
COPY sample-data/callradar-data/metadata sample-data/callradar-data/metadata
COPY --from=web-build /app/apps/web/dist apps/web/dist

RUN pip install --no-cache-dir -e apps/api \
    && mkdir -p /app/data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "apps/api/src", "--host", "0.0.0.0", "--port", "8000"]
