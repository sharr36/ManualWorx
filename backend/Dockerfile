FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install shared package first
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install backend dependencies
COPY backend/pyproject.toml /app/
RUN pip install --no-cache-dir .

# Copy application code
COPY backend/app/ /app/app/
COPY backend/migrations/ /app/migrations/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
