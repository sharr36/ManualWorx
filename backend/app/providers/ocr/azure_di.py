"""Azure Document Intelligence OCR provider (optional upgrade)."""

from .base import LayoutResult, OCRProvider, OCRResult, Table


class NotConfiguredError(Exception):
    pass


class AzureDIProvider(OCRProvider):
    """OCR using Azure Document Intelligence for superior diagram/table extraction."""

    def __init__(self, endpoint: str, key: str):
        if not endpoint or not key:
            raise NotConfiguredError(
                "Azure DI requires AZURE_DI_ENDPOINT and AZURE_DI_KEY"
            )
        self.endpoint = endpoint
        self.key = key

    async def extract_text(self, pdf_bytes: bytes, page_number: int) -> OCRResult:
        # TODO: Implement Azure DI text extraction
        # Uses azure-ai-documentintelligence SDK
        raise NotImplementedError("Azure DI text extraction not yet implemented")

    async def extract_tables(self, pdf_bytes: bytes, page_number: int) -> list[Table]:
        # TODO: Implement Azure DI table extraction
        raise NotImplementedError("Azure DI table extraction not yet implemented")

    async def analyze_layout(self, pdf_bytes: bytes, page_number: int) -> LayoutResult:
        # TODO: Implement Azure DI layout analysis
        raise NotImplementedError("Azure DI layout analysis not yet implemented")
