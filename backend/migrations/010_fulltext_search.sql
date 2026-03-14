-- Migration 010: Full-text search indexes for pages and chunks

-- GIN index on pages.extracted_text for full-text search
CREATE INDEX IF NOT EXISTS idx_pages_text_search
    ON pages USING GIN (to_tsvector('english', COALESCE(extracted_text, '')));

-- GIN index on chunks.chunk_text for full-text search
CREATE INDEX IF NOT EXISTS idx_chunks_text_search
    ON chunks USING GIN (to_tsvector('english', COALESCE(chunk_text, '')));

-- Composite index for manual-scoped page text search
CREATE INDEX IF NOT EXISTS idx_pages_manual_text
    ON pages (manual_id)
    INCLUDE (page_number, classification);
