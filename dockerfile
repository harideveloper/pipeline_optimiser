FROM python:3.11-slim AS base

# fix : Copy Zscaler root CA (local docker) due to zcaler proxy blocking requests
COPY zscaler-root-ca.crt /usr/local/share/ca-certificates/zscaler-root-ca.crt
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    postgresql-client \
    libpq-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates


RUN echo "CA certificates count:" && \
    grep -c "BEGIN CERTIFICATE" /etc/ssl/certs/ca-certificates.crt || echo "0"

WORKDIR /app
RUN useradd -m -u 1000 pipeline && chown -R pipeline:pipeline /app
USER pipeline

FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# debug: Append Zscaler cert to certifi's bundle (as pipeline user)
RUN python -c "import certifi; print(certifi.where())" && \
    cat /usr/local/share/ca-certificates/zscaler-root-ca.crt >> $(python -c "import certifi; print(certifi.where())") && \
    echo "Zscaler certificate added to certifi bundle"

# debug: verify the cert was added
RUN python -c "import certifi; import os; bundle=certifi.where(); print(f'Certifi bundle: {bundle}'); print(f'Exists: {os.path.exists(bundle)}'); print(f'Size: {os.path.getsize(bundle)} bytes')"


# Final stage
FROM base AS final

COPY --from=deps /home/pipeline/.local /home/pipeline/.local
COPY --chown=pipeline:pipeline . .

ENV PATH="/home/pipeline/.local/bin:$PATH"

# temporary - to be removed 
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8091/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8091", "--workers", "4"]