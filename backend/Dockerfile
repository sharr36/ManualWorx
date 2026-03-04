FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install shared package
COPY _shared/ /shared/
RUN pip install --no-cache-dir /shared/ && rm -rf /shared/

# Install backend deps explicitly (shared already installed above;
# file:// reference in pyproject.toml only works for local dev)
COPY pyproject.toml /app/
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0" "asyncpg>=0.29.0" \
    "pydantic>=2.0" "pydantic-settings>=2.0" "email-validator>=2.0.0" "argon2-cffi>=23.1.0" \
    "python-multipart>=0.0.9" "stripe>=8.0.0" "httpx>=0.27.0" \
    "anthropic>=0.39.0" "boto3>=1.35.0" "qdrant-client>=1.12.0" \
    "arq>=0.26.0" "PyMuPDF>=1.24.0" "Jinja2>=3.1.0" "redis>=5.0.0"

# Copy application code
COPY app/ /app/app/
COPY migrations/ /app/migrations/

RUN useradd -r -s /bin/false appuser

EXPOSE 8000

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
