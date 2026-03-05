FROM python:3.11-slim

# System deps for weasyprint
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        libcairo2 libffi-dev shared-mime-info && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install shared package
COPY shared/ /app/shared/
RUN pip install --no-cache-dir /app/shared/ && rm -rf /app/shared/

# Install docgen deps explicitly (shared already installed above;
# file:// reference in pyproject.toml only works for local dev)
RUN pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn>=0.30" "weasyprint>=62" \
    "python-docx>=1.1" "Jinja2>=3.1" "httpx>=0.27"

# Copy docgen application code
COPY docgen/app/ /app/app/

RUN useradd -r -s /bin/false appuser

EXPOSE 8001

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
