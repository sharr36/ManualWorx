"""OCR processing wrapper — batches pages through OCR provider."""


class OCRProcessor:
    """Wraps an OCR provider with batch processing and progress tracking."""

    def __init__(self, provider):
        self.provider = provider

    async def process_page(self, pdf_bytes: bytes, page_number: int) -> dict:
        """OCR a single page and return structured results."""
        # TODO: Implement in Phase 1
        raise NotImplementedError

    async def process_batch(self, pdf_bytes: bytes, page_numbers: list[int]) -> list[dict]:
        """OCR multiple pages with concurrency control."""
        # TODO: Implement in Phase 1
        raise NotImplementedError
