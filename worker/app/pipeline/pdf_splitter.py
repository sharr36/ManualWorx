"""PDF splitting utility — converts PDF pages to images."""

from dataclasses import dataclass


@dataclass
class PageImage:
    page_number: int
    image_bytes: bytes
    width: int
    height: int


class PDFSplitter:
    """Split a PDF into individual page images using pdf2image."""

    def __init__(self, dpi: int = 300):
        self.dpi = dpi

    async def split(self, pdf_path: str) -> list[PageImage]:
        """Split a PDF file into page images.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of PageImage objects.
        """
        # TODO: Implement in Phase 1
        # from pdf2image import convert_from_path
        # images = convert_from_path(pdf_path, dpi=self.dpi)
        # return [PageImage(page_number=i, image_bytes=..., width=..., height=...) for i, img in enumerate(images)]
        raise NotImplementedError("PDF splitting not yet implemented")
