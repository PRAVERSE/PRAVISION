# ==============================================================================
# PRAVISION - Universal OSINT & Intelligence Platform
# Production Multi-Stage Container Image
# ==============================================================================

# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci --quiet

COPY frontend/ ./
RUN npm run build

# Stage 2: Python Backend Runtime
FROM python:3.12-slim AS runner

# Create non-root unprivileged operator user
RUN groupadd -g 10001 pravision && \
    useradd -u 10001 -g pravision -m -s /bin/bash pravision

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy built frontend distribution into static serving location
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy backend application source
COPY backend /app/backend

# Create runtime directories for evidence vault, archives, and local SQLite fallback
RUN mkdir -p /app/backend/data/vault /app/backend/data/archives /app/backend/data/backups && \
    chown -R pravision:pravision /app

# Switch to non-root user
USER pravision

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORKSPACE_DIR=/app/backend \
    PORT=8000 \
    HOST=0.0.0.0

EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/api/storage/status || exit 1

WORKDIR /app/backend

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

