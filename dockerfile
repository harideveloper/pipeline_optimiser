# ============================================
# Base stage
# ============================================
FROM python:3.11-slim AS base
COPY zscaler-root-ca.crt /usr/local/share/ca-certificates/zscaler-root-ca.crt

# Install system dependencies + SSL + OpenSSL certs
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    postgresql-client \
    libpq-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Verify CA bundle was updated
RUN echo "CA certificates count:" && \
    grep -c "BEGIN CERTIFICATE" /etc/ssl/certs/ca-certificates.crt || echo "0"

# Set working directory
WORKDIR /app

# Create non-root user AFTER certs are installed
RUN useradd -m -u 1000 pipeline && chown -R pipeline:pipeline /app

# Switch to non-root user
USER pipeline

# ============================================
# Install dependencies
# ============================================
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ============================================
# Final stage
# ============================================
FROM base AS final
COPY --from=deps /home/pipeline/.local /home/pipeline/.local
COPY --chown=pipeline:pipeline . .

ENV PATH="/home/pipeline/.local/bin:$PATH"

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8091/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091", "--workers", "4"]
