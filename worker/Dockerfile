FROM python:3.11-slim

# System deps for pdf2image and Tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-eng && \
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
    "pydantic-settings>=2.0" "pytesseract>=0.3.10" "anthropic>=0.39.0"

# Copy worker application code
COPY worker/app/ /app/app/

# Verify all imports work at build time (catches missing deps early)
RUN python -c "import fitz; print(f'PyMuPDF {fitz.version_bind} OK'); \
from app.pipeline.ocr_processor import OCRProcessor; \
from app.pipeline.pdf_splitter import PDFSplitter; \
from app.pipeline.chunker import Chunker; \
from app.pipeline.embedder import Embedder; \
print('All worker imports OK')"

RUN useradd -r -s /bin/false appuser

USER appuser

CMD ["arq", "app.main.WorkerSettings"]
