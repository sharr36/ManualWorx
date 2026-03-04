"""PDF splitting utility — extracts pages from PDF using PyMuPDF."""

from dataclasses import dataclass

import fitz


@dataclass
class PageImage:
    page_number: int
    image_bytes: bytes
    width: int
    height: int


class PDFSplitter:
    """Split a PDF into individual page images using PyMuPDF (fitz)."""

    def __init__(self, dpi: int = 300):
        self.dpi = dpi
        self._zoom = dpi / 72.0

    def get_page_count(self, pdf_bytes: bytes) -> int:
        """Get the number of pages in a PDF."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        count = len(doc)
        doc.close()
        return count

    def split(self, pdf_bytes: bytes) -> list[PageImage]:
        """Split a PDF into page images rendered as PNG.

        Args:
            pdf_bytes: Raw PDF file bytes.

        Returns:
            List of PageImage objects with PNG image bytes.
        """
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        mat = fitz.Matrix(self._zoom, self._zoom)

        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(matrix=mat)
            png_bytes = pix.tobytes("png")
            pages.append(
                PageImage(
                    page_number=i,
                    image_bytes=png_bytes,
                    width=pix.width,
                    height=pix.height,
                )
            )

        doc.close()
        return pages

    def extract_page_text(self, pdf_bytes: bytes, page_number: int) -> str:
        """Extract raw text from a specific page."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_number >= len(doc):
            doc.close()
            return ""
        text = doc[page_number].get_text("text")
        doc.close()
        return text
