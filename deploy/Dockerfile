# Multi-stage build: frontend (node) -> backend (python slim).
# Build context = repository root:
#   docker build -f deploy/Dockerfile -t eafc-intelligence .
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --uid 10001 eafc
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt gunicorn
COPY backend/ backend/
COPY scripts/ scripts/
COPY db/ db/
COPY data/ data/
COPY --from=frontend /fe/dist /app/frontend/dist
USER eafc
EXPOSE 8000
ENV FRONTEND_DIST=/app/frontend/dist
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"
CMD ["python", "-m", "gunicorn", "backend.api.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", \
     "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
