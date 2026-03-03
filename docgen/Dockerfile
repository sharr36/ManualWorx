FROM python:3.11-slim

# System deps for weasyprint
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
        libcairo2 libffi-dev shared-mime-info && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY shared/ /app/shared/
RUN pip install --no-cache-dir /app/shared/

COPY docgen/ /app/docgen/
RUN pip install --no-cache-dir /app/docgen/

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
