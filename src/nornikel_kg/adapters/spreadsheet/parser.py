from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any

from nornikel_kg.ports.parser import (
    ParsedDocument,
    ParsedTable,
    ParsedTableCell,
    ParsedTableRow,
    ParserError,
)

logger = logging.getLogger(__name__)

_SUPPORTED_EXTENSIONS = {".xlsx", ".xls"}

# Caps keep the ledger from swallowing a whole data-lake, but the previous
# 20/300/30 defaults gutted real reference workbooks. Defaults are raised and
# every cap is env-overridable (batch ingest can lift them further).
_DEFAULT_MAX_SHEETS = 50
_DEFAULT_MAX_ROWS_PER_SHEET = 5000
_DEFAULT_MAX_COLUMNS = 60


def _cap(env_name: str, default: int) -> int:
    raw = os.getenv(env_name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class SpreadsheetDocumentParser:
    """XLSX/XLS -> table-row evidence spans with sheet/row provenance."""

    parser_profile = "spreadsheet_v1"

    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        extension = Path(filename).suffix.lower()
        if extension not in _SUPPORTED_EXTENSIONS:
            raise ParserError(f"Unsupported spreadsheet extension: {extension}")
        import pandas as pd

        try:
            sheets: dict[str, Any] = pd.read_excel(
                io.BytesIO(content), sheet_name=None, header=None, dtype=str
            )
        except Exception as error:
            raise ParserError(f"Spreadsheet parse failed for {filename}: {error}") from error

        max_sheets = _cap("INGEST_XLSX_MAX_SHEETS", _DEFAULT_MAX_SHEETS)
        max_rows = _cap("INGEST_XLSX_MAX_ROWS", _DEFAULT_MAX_ROWS_PER_SHEET)
        max_columns = _cap("INGEST_XLSX_MAX_COLUMNS", _DEFAULT_MAX_COLUMNS)
        tables: list[ParsedTable] = []
        truncated_rows = 0
        for table_index, (sheet_name, frame) in enumerate(sheets.items(), start=1):
            if table_index > max_sheets:
                break
            frame = frame.fillna("")
            rows: list[ParsedTableRow] = []
            for row_index, row in enumerate(frame.itertuples(index=False), start=1):
                if row_index > max_rows:
                    truncated_rows += len(frame) - max_rows
                    break
                cells = [
                    ParsedTableCell(
                        text=str(value).strip(),
                        row_index=row_index,
                        col_index=col_index,
                    )
                    for col_index, value in enumerate(row[:max_columns], start=1)
                ]
                if any(cell.text for cell in cells):
                    rows.append(ParsedTableRow(cells=cells, row_index=row_index))
            if rows:
                # Sheet name as a header row keeps the sheet topic citable.
                tables.append(ParsedTable(rows=rows, table_index=table_index, page=None))
                logger.debug("Sheet %s: %d rows", sheet_name, len(rows))
        metadata: dict[str, Any] = {"sheet_count": len(sheets)}
        if truncated_rows > 0:
            metadata["truncated_rows"] = truncated_rows
        return ParsedDocument(
            blocks=[],
            tables=tables,
            title=Path(filename).stem,
            parser_profile=self.parser_profile,
            metadata=metadata,
        )
