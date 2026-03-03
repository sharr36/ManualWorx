"""Manual ingestion orchestrator task."""


async def ingest_manual(ctx: dict, manual_id: str, tenant_id: str) -> dict:
    """Orchestrate the full manual ingestion pipeline.

    Steps:
    1. Download PDF from storage
    2. Split into individual pages (pdf2image)
    3. OCR each page (PyMuPDF or Azure DI)
    4. Classify each page (text, schematic, table, etc.)
    5. Chunk text for embedding
    6. Generate embeddings and upsert to Qdrant
    7. Update manual status to 'ready'

    Progress is tracked via Redis pub/sub for real-time UI updates.
    """
    # TODO: Implement in Phase 1
    # redis = ctx.get("redis")
    # pool = ctx.get("pool")
    #
    # 1. Update status to 'processing'
    # 2. Download PDF from S3/Tigris
    # 3. Split pages with PDFSplitter
    # 4. For each page (with concurrency limit):
    #    a. OCR with OCRProcessor
    #    b. Classify with PageClassifier
    #    c. Store extracted text in pages table
    #    d. Upload page image to S3
    # 5. Chunk all text with Chunker
    # 6. Generate embeddings with Embedder
    # 7. Upsert vectors to Qdrant
    # 8. Update status to 'ready'
    # 9. Publish completion event
    return {"status": "not_implemented", "manual_id": manual_id}
