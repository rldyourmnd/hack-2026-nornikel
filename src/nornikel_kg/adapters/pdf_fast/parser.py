from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from nornikel_kg.ports.parser import (
    NoTextLayerError,
    ParsedBlock,
    ParsedDocument,
    ParserError,
)

logger = logging.getLogger(__name__)

# Block size for splitting page text into retrievable spans.
_MAX_BLOCK_CHARS = 800


def _chunk_page_text(text: str, max_chars: int) -> list[str]:
    """Group a page's lines into ~max_chars blocks on line boundaries."""
    chunks: list[str] = []
    buffer: list[str] = []
    size = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if size + len(line) > max_chars and buffer:
            chunks.append(" ".join(buffer))
            buffer, size = [], 0
        buffer.append(line)
        size += len(line) + 1
    if buffer:
        chunks.append(" ".join(buffer))
    return chunks


class PyPdfiumFastParser:
    """Fast, ML-free PDF text extraction via pypdfium2 — no GPU, no layout model.

    For text-layer PDFs this replaces the Docling ML pipeline (layout +
    TableFormer), which is CPU-bound and slow with no hardware acceleration
    (NNPACK unavailable on the stand). Text-only: a table's content is captured
    as text lines (numbers stay inline, so retrieval + LLM/dictionary extraction
    still see them) but not as structured numeric-fact rows. Scanned PDFs (no
    text layer) raise NoTextLayerError — OCR is out of scope.
    """

    parser_profile = "pypdfium_fast_v1"

    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        extension = Path(filename).suffix.lower()
        if extension != ".pdf":
            raise ParserError(f"PyPdfiumFastParser handles .pdf only, got {extension}")
        import pypdfium2 as pdfium

        try:
            pdf: Any = pdfium.PdfDocument(content)
        except Exception as error:
            raise ParserError(f"pypdfium2 could not open {filename}: {error}") from error

        blocks: list[ParsedBlock] = []
        ordinal = 0
        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]
                textpage = page.get_textpage()
                try:
                    text = textpage.get_text_range()
                finally:
                    textpage.close()
                    page.close()
                for chunk in _chunk_page_text(text, _MAX_BLOCK_CHARS):
                    ordinal += 1
                    blocks.append(
                        ParsedBlock(
                            text=chunk, page=page_index + 1, locator=f"block_{ordinal}"
                        )
                    )
        finally:
            pdf.close()

        parsed = ParsedDocument(
            blocks=blocks,
            tables=[],
            title=Path(filename).stem,
            parser_profile=self.parser_profile,
        )
        if not parsed.has_content:
            raise NoTextLayerError(
                f"PDF {filename} has no extractable text layer (OCR is out of scope)."
            )
        return parsed
