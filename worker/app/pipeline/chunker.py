"""Text chunking — splits extracted text into embeddable chunks."""


class Chunker:
    """Hybrid page-level + paragraph-level chunking.

    Strategy:
    - Full page text as one chunk (for broad context)
    - Individual paragraphs as separate chunks (for precise retrieval)
    - Tables as structured chunks with header context
    - Overlap between consecutive chunks for continuity
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    async def chunk_page(self, page_text: str, page_number: int) -> list[dict]:
        """Chunk a single page's text.

        Returns:
            List of {chunk_index, chunk_text, token_count} dicts.
        """
        # TODO: Implement in Phase 1
        raise NotImplementedError

    async def chunk_manual(self, pages: list[dict]) -> list[dict]:
        """Chunk all pages in a manual."""
        # TODO: Implement in Phase 1
        raise NotImplementedError
