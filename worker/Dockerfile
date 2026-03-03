FROM python:3.11-slim

# System deps for pdf2image
RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared package first
COPY shared/ /app/shared/
RUN pip install --no-cache-dir /app/shared/

# Install worker
COPY worker/ /app/worker/
RUN pip install --no-cache-dir /app/worker/

CMD ["arq", "app.main.WorkerSettings"]
