FROM python:3.11-slim

# System deps for pdf2image
RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared package
COPY shared/ /app/shared/
RUN pip install --no-cache-dir /app/shared/ && rm -rf /app/shared/

# Install worker deps explicitly (shared already installed above;
# file:// reference in pyproject.toml only works for local dev)
RUN pip install --no-cache-dir \
    "arq>=0.26" "asyncpg>=0.29" "redis>=5.0" "PyMuPDF>=1.24" \
    "Pillow>=10.0" "httpx>=0.27" "boto3>=1.35" "qdrant-client>=1.12" \
    "pydantic-settings>=2.0"

# Copy worker application code
COPY worker/ /app/worker/

RUN useradd -r -s /bin/false appuser

USER appuser

CMD ["arq", "app.main.WorkerSettings"]
