"""PDF generation using WeasyPrint."""

from weasyprint import HTML


def generate_pdf(html_content: str) -> bytes:
    """Convert HTML content to PDF bytes."""
    html = HTML(string=html_content)
    return html.write_pdf()
