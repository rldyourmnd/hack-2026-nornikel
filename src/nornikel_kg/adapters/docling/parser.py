from __future__ import annotations

import io
import logging
import os
import queue
import threading
from pathlib import Path
from typing import Any

from nornikel_kg.ports.parser import (
    NoTextLayerError,
    ParsedBlock,
    ParsedDocument,
    ParsedTable,
    ParsedTableCell,
    ParsedTableRow,
    ParserError,
)

logger = logging.getLogger(__name__)

# Docling's converter holds shared ML models and is NOT thread-safe, so parallel
# parsing uses a pool of DISTINCT converters (each used by one thread at a time),
# sized by DOCLING_PARSE_WORKERS (default 1 = serialized, safe for the API; the
# batch sets it higher to use more cores).
_PARSE_WORKERS = max(1, int(os.getenv("DOCLING_PARSE_WORKERS", "1")))
_pool: queue.Queue[Any] | None = None
_pool_lock = threading.Lock()


def _converter_pool() -> queue.Queue[Any]:
    global _pool
    with _pool_lock:
        if _pool is None:
            built: queue.Queue[Any] = queue.Queue()
            for _ in range(_PARSE_WORKERS):
                built.put(_build_converter())
            _pool = built
    return _pool

# .docm is the same OOXML container as .docx (macros are ignored by Docling);
# the stream name is rewritten so format detection stays on the DOCX path.
_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".docm", ".pptx"}


def _build_converter() -> Any:
    """Build a Docling converter (expensive model load; converters are pooled)."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pdf_options = PdfPipelineOptions()
    pdf_options.do_ocr = False
    pdf_options.do_table_structure = True
    # FAST TableFormer, no cell-bbox matching: ~2-3x faster tables; downstream
    # reads row text, not cell geometry.
    pdf_options.table_structure_options.mode = TableFormerMode.FAST
    pdf_options.table_structure_options.do_cell_matching = False
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX, InputFormat.PPTX],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)},
    )


class DoclingDocumentParser:
    """PDF (text layer only) and DOCX parser producing provenance-carrying spans."""

    parser_profile = "docling_v1"

    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        extension = Path(filename).suffix.lower()
        if extension not in _SUPPORTED_EXTENSIONS:
            raise ParserError(f"Unsupported parser extension: {extension}")

        from docling.datamodel.base_models import ConversionStatus, DocumentStream

        stream_name = (
            f"{Path(filename).stem}.docx" if extension == ".docm" else filename
        )
        stream = DocumentStream(name=stream_name, stream=io.BytesIO(content))
        pool = _converter_pool()
        converter = pool.get()
        try:
            result = converter.convert(stream, raises_on_error=True)
        except Exception as error:  # docling raises many concrete types
            raise ParserError(f"Docling failed to parse {filename}: {error}") from error
        finally:
            pool.put(converter)
        if result.status not in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
            raise ParserError(f"Docling conversion status {result.status} for {filename}")

        document = result.document
        blocks = self._collect_blocks(document)
        tables = self._collect_tables(document)
        parsed = ParsedDocument(
            blocks=blocks,
            tables=tables,
            title=self._document_title(document, filename),
            parser_profile=self.parser_profile,
        )
        if extension == ".pdf" and not parsed.has_content:
            raise NoTextLayerError(
                f"PDF {filename} has no extractable text layer (OCR is out of scope)."
            )
        if not parsed.has_content:
            raise ParserError(f"Document {filename} produced no extractable content.")
        return parsed

    def _collect_blocks(self, document: Any) -> list[ParsedBlock]:
        blocks: list[ParsedBlock] = []
        block_ordinal = 0
        for item, _level in document.iterate_items():
            text = getattr(item, "text", None)
            if not text or not str(text).strip():
                continue
            page, bbox = self._provenance(item)
            block_ordinal += 1
            locator = f"block_{block_ordinal}"
            if bbox is not None:
                locator = f"{locator}:bbox_{bbox}"
            blocks.append(ParsedBlock(text=str(text).strip(), page=page, locator=locator))
        return blocks

    def _collect_tables(self, document: Any) -> list[ParsedTable]:
        tables: list[ParsedTable] = []
        for table_index, table_item in enumerate(getattr(document, "tables", []) or [], start=1):
            page, _bbox = self._provenance(table_item)
            header, rows = self._table_rows(table_item)
            if rows:
                tables.append(
                    ParsedTable(rows=rows, table_index=table_index, page=page, header=header)
                )
        return tables

    def _table_rows(self, table_item: Any) -> tuple[list[str], list[ParsedTableRow]]:
        grid = getattr(getattr(table_item, "data", None), "grid", None)
        if not grid:
            return [], []
        # Header = first grid row with >=2 non-empty cells (skip title/blank rows).
        header_idx = next(
            (
                i
                for i, r in enumerate(grid)
                if sum(bool(str(getattr(c, "text", "") or "").strip()) for c in r) >= 2
            ),
            next(
                (
                    i
                    for i, r in enumerate(grid)
                    if any(str(getattr(c, "text", "") or "").strip() for c in r)
                ),
                0,
            ),
        )
        header = (
            [str(getattr(cell, "text", "") or "").strip() for cell in grid[header_idx]]
            if grid else []
        )
        rows: list[ParsedTableRow] = []
        for row_index, grid_row in enumerate(grid[header_idx + 1 :], start=header_idx + 2):
            cells = [
                ParsedTableCell(
                    text=str(getattr(cell, "text", "") or "").strip(),
                    row_index=row_index,
                    col_index=col_index,
                    header=header[col_index - 1] if col_index - 1 < len(header) else "",
                )
                for col_index, cell in enumerate(grid_row, start=1)
            ]
            if any(cell.text for cell in cells):
                rows.append(ParsedTableRow(cells=cells, row_index=row_index, headers=header))
        return header, rows

    def _provenance(self, item: Any) -> tuple[int | None, str | None]:
        provenance = getattr(item, "prov", None) or []
        for entry in provenance:
            page = getattr(entry, "page_no", None)
            bbox = getattr(entry, "bbox", None)
            bbox_text: str | None = None
            if bbox is not None:
                left = getattr(bbox, "l", None)
                top = getattr(bbox, "t", None)
                if left is not None and top is not None:
                    bbox_text = f"{left:.0f}x{top:.0f}"
            if page is not None:
                return int(page), bbox_text
        return None, None

    def _document_title(self, document: Any, filename: str) -> str:
        name = getattr(document, "name", None)
        if name and str(name).strip() and str(name) != "file":
            return str(name)
        return Path(filename).stem
