"""Text chunking — splits extracted text into embeddable chunks."""


class Chunker:
    """Hybrid page-level + paragraph-level chunking.

    Strategy:
    - Full page text as chunk_index=0 (for broad context retrieval)
    - Paragraph-level chunks with overlap (for precise retrieval)
    - Token estimation via word count
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def _token_count(self, text: str) -> int:
        """Estimate token count from word count."""
        return len(text.split())

    def chunk_page(self, page_text: str, page_number: int) -> list[dict]:
        """Chunk a single page's text.

        Returns:
            List of {chunk_index, chunk_text, token_count} dicts.
        """
        text = page_text.strip()
        if not text:
            return []

        chunks = []
        token_count = self._token_count(text)

        # Chunk 0: full page text (if not too large)
        if token_count <= 2048:
            chunks.append({
                "chunk_index": 0,
                "chunk_text": text,
                "token_count": token_count,
            })

        # Paragraph-level chunks
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        current_chunk = ""
        current_tokens = 0
        chunk_index = 1
        overlap_text = ""

        for para in paragraphs:
            para_tokens = self._token_count(para)

            # If a single paragraph exceeds chunk_size, split it by sentences
            if para_tokens > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append({
                        "chunk_index": chunk_index,
                        "chunk_text": current_chunk.strip(),
                        "token_count": current_tokens,
                    })
                    # Save overlap from end of current chunk
                    words = current_chunk.strip().split()
                    overlap_text = " ".join(words[-self.overlap:]) if len(words) > self.overlap else current_chunk.strip()
                    chunk_index += 1
                    current_chunk = ""
                    current_tokens = 0

                # Split long paragraph by sentences
                sentences = self._split_sentences(para)
                for sentence in sentences:
                    sent_tokens = self._token_count(sentence)
                    if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                        chunks.append({
                            "chunk_index": chunk_index,
                            "chunk_text": (overlap_text + " " + current_chunk).strip() if overlap_text else current_chunk.strip(),
                            "token_count": self._token_count(overlap_text) + current_tokens if overlap_text else current_tokens,
                        })
                        words = current_chunk.strip().split()
                        overlap_text = " ".join(words[-self.overlap:]) if len(words) > self.overlap else current_chunk.strip()
                        chunk_index += 1
                        current_chunk = sentence
                        current_tokens = sent_tokens
                    else:
                        current_chunk = (current_chunk + " " + sentence).strip() if current_chunk else sentence
                        current_tokens += sent_tokens
                continue

            # Normal case: merge paragraphs until chunk_size
            if current_tokens + para_tokens > self.chunk_size and current_chunk:
                chunk_text = (overlap_text + " " + current_chunk).strip() if overlap_text else current_chunk.strip()
                chunks.append({
                    "chunk_index": chunk_index,
                    "chunk_text": chunk_text,
                    "token_count": self._token_count(chunk_text),
                })
                words = current_chunk.strip().split()
                overlap_text = " ".join(words[-self.overlap:]) if len(words) > self.overlap else current_chunk.strip()
                chunk_index += 1
                current_chunk = para
                current_tokens = para_tokens
            else:
                current_chunk = (current_chunk + "\n\n" + para).strip() if current_chunk else para
                current_tokens += para_tokens

        # Flush remaining
        if current_chunk:
            chunk_text = (overlap_text + " " + current_chunk).strip() if overlap_text else current_chunk.strip()
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "token_count": self._token_count(chunk_text),
            })

        # Skip paragraph chunks if only one chunk and it duplicates full page
        if len(chunks) == 2 and chunks[0]["chunk_text"] == chunks[1]["chunk_text"]:
            chunks = [chunks[0]]

        return chunks

    def chunk_manual(self, pages: list[dict]) -> list[dict]:
        """Chunk all pages in a manual.

        Args:
            pages: List of {page_id, page_number, text, classification} dicts.

        Returns:
            List of chunk dicts with page metadata added.
        """
        all_chunks = []
        for page in pages:
            page_chunks = self.chunk_page(page["text"], page["page_number"])
            for chunk in page_chunks:
                chunk["page_id"] = page["page_id"]
                chunk["page_number"] = page["page_number"]
                chunk["classification"] = page.get("classification", "text")
                all_chunks.append(chunk)
        return all_chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences (simple approach)."""
        import re
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p for p in parts if p.strip()]
