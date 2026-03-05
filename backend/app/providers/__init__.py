"""Provider factory functions — abstracted external dependencies."""

import logging

from ..config import settings
from .ocr.base import OCRProvider

logger = logging.getLogger(__name__)


def _build_ocr_provider(name: str) -> OCRProvider:
    """Instantiate a single OCR provider by name."""
    if name == "tesseract":
        from .ocr.tesseract import TesseractProvider
        return TesseractProvider()
    elif name == "claude_vision":
        from .ocr.claude_vision import ClaudeVisionProvider
        return ClaudeVisionProvider(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.CLAUDE_VISION_MODEL,
        )
    elif name == "unstructured":
        from .ocr.unstructured import UnstructuredProvider
        return UnstructuredProvider(
            api_url=settings.UNSTRUCTURED_API_URL,
            api_key=settings.UNSTRUCTURED_API_KEY,
        )
    elif name == "reducto":
        from .ocr.reducto import ReductoProvider
        return ReductoProvider(api_key=settings.REDUCTO_API_KEY)
    elif name == "pymupdf":
        from .ocr.pymupdf import PyMuPDFProvider
        return PyMuPDFProvider()
    else:
        logger.warning("Unknown OCR provider %r, falling back to pymupdf", name)
        from .ocr.pymupdf import PyMuPDFProvider
        return PyMuPDFProvider()


def get_ocr_provider() -> "FallbackOCRProvider":
    """Get the configured OCR provider with fallback support."""
    primary = _build_ocr_provider(settings.OCR_PROVIDER)
    fallback = None
    if settings.OCR_FALLBACK_PROVIDER and settings.OCR_FALLBACK_PROVIDER != settings.OCR_PROVIDER:
        fallback = _build_ocr_provider(settings.OCR_FALLBACK_PROVIDER)
    return FallbackOCRProvider(
        primary=primary,
        fallback=fallback,
        threshold=settings.OCR_FALLBACK_THRESHOLD,
    )


class FallbackOCRProvider(OCRProvider):
    """Wraps a primary provider and falls back to a secondary when confidence is low."""

    def __init__(
        self,
        primary: OCRProvider,
        fallback: OCRProvider | None,
        threshold: float = 0.5,
    ):
        self.primary = primary
        self.fallback = fallback
        self.threshold = threshold

    async def extract_text(self, pdf_bytes: bytes, page_number: int):
        result = await self.primary.extract_text(pdf_bytes, page_number)
        if result.confidence >= self.threshold or not self.fallback:
            return result
        logger.info(
            "Primary OCR confidence %.2f < %.2f for page %d, trying fallback",
            result.confidence, self.threshold, page_number,
        )
        return await self.fallback.extract_text(pdf_bytes, page_number)

    async def extract_tables(self, pdf_bytes: bytes, page_number: int):
        tables = await self.primary.extract_tables(pdf_bytes, page_number)
        if tables or not self.fallback:
            return tables
        return await self.fallback.extract_tables(pdf_bytes, page_number)

    async def analyze_layout(self, pdf_bytes: bytes, page_number: int):
        return await self.primary.analyze_layout(pdf_bytes, page_number)


def get_embedding_provider():
    """Get the configured embedding provider."""
    if settings.EMBEDDING_PROVIDER == "self_hosted" and settings.EMBEDDING_SERVICE_URL:
        from .embedding.self_hosted import SelfHostedEmbeddingProvider
        return SelfHostedEmbeddingProvider(settings.EMBEDDING_SERVICE_URL)
    from .embedding.together import TogetherEmbeddingProvider
    return TogetherEmbeddingProvider(settings.TOGETHER_API_KEY)


def get_storage_provider():
    """Get the configured storage provider."""
    from .storage.tigris import TigrisStorageProvider
    return TigrisStorageProvider(
        endpoint_url=settings.AWS_ENDPOINT_URL_S3,
        access_key=settings.AWS_ACCESS_KEY_ID,
        secret_key=settings.AWS_SECRET_ACCESS_KEY,
        bucket=settings.BUCKET_NAME,
    )


def get_vector_provider():
    """Get the configured vector provider."""
    from .vector.qdrant import QdrantVectorProvider
    return QdrantVectorProvider(settings.QDRANT_URL)
