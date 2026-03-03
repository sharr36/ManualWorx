"""ManualWorx document generation service."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

from .generators.docx_generator import generate_docx
from .generators.pdf_generator import generate_pdf

app = FastAPI(title="ManualWorx DocGen", version="0.1.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
STYLES_DIR = Path(__file__).parent / "styles"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)


class GenerateRequest(BaseModel):
    doc_type: str  # troubleshooting_guide, service_procedure, etc.
    format: str = "pdf"  # pdf or docx
    content: dict  # Template-specific content data
    title: str = "ManualWorx Document"


@app.post("/generate")
async def generate(body: GenerateRequest) -> Response:
    """Generate a document from content data."""
    template_name = f"{body.doc_type}.html"

    try:
        template = _jinja_env.get_template(template_name)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown document type: {body.doc_type}",
        )

    # Load brand CSS
    css_path = STYLES_DIR / "manualworx.css"
    brand_css = css_path.read_text() if css_path.exists() else ""

    html_content = template.render(
        title=body.title,
        brand_css=brand_css,
        **body.content,
    )

    if body.format == "pdf":
        pdf_bytes = generate_pdf(html_content)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{body.title}.pdf"'},
        )
    elif body.format == "docx":
        docx_bytes = generate_docx(body.content, body.title)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{body.title}.docx"'},
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {body.format}")


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "docgen"}
