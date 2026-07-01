# Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Build backend
FROM python:3.12-slim AS backend
WORKDIR /app

ARG APP_VERSION=dev
ARG BUILD_TIME=
ARG DOCKER_IMAGE_REPO=ashiepleb/homelab-dns-manager
ENV APP_VERSION=${APP_VERSION}
ENV BUILD_TIME=${BUILD_TIME}
ENV DOCKER_IMAGE_REPO=${DOCKER_IMAGE_REPO}
LABEL org.opencontainers.image.version="${APP_VERSION}"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/data && chmod 755 /app/data \
    && chmod +x /app/backend/docker-entrypoint.sh

ENV PYTHONPATH=/app/backend
ENV DATABASE_URL=sqlite+aiosqlite:////app/data/homelab_dns.db
WORKDIR /app/backend

EXPOSE 8000

CMD ["/app/backend/docker-entrypoint.sh"]
