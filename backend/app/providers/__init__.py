"""Provider factory functions — abstracted external dependencies."""

from ..config import settings


def get_ocr_provider():
    """Get the configured OCR provider."""
    if settings.AZURE_DI_ENDPOINT and settings.AZURE_DI_KEY:
        from .ocr.azure_di import AzureDIProvider
        return AzureDIProvider(settings.AZURE_DI_ENDPOINT, settings.AZURE_DI_KEY)
    from .ocr.pymupdf import PyMuPDFProvider
    return PyMuPDFProvider()


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
