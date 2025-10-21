# Dockerfile
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 pipeline && \
    chown -R pipeline:pipeline /app

# ============================================
# Development stage
# ============================================
FROM base as development

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install dev dependencies
RUN pip install --no-cache-dir \
    pytest==7.4.0 \
    pytest-cov==4.1.0 \
    black==23.7.0 \
    ruff==0.0.285

USER pipeline

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091", "--reload"]

# ============================================
# Production stage
# ============================================
FROM base as production

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=pipeline:pipeline . .

USER pipeline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8091/health').raise_for_status()"

EXPOSE 8091

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091", "--workers", "4"]