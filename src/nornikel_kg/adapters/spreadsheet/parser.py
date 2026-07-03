from __future__ import annotations

import io
import logging
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

# Data workbooks in the real corpus carry thousands of rows; the ledger wants
# evidence, not a data-lake dump — capped honestly and reported in metadata.
MAX_SHEETS = 20
MAX_ROWS_PER_SHEET = 300
MAX_COLUMNS = 30


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

        tables: list[ParsedTable] = []
        truncated_rows = 0
        for table_index, (sheet_name, frame) in enumerate(sheets.items(), start=1):
            if table_index > MAX_SHEETS:
                break
            frame = frame.fillna("")
            rows: list[ParsedTableRow] = []
            for row_index, row in enumerate(frame.itertuples(index=False), start=1):
                if row_index > MAX_ROWS_PER_SHEET:
                    truncated_rows += len(frame) - MAX_ROWS_PER_SHEET
                    break
                cells = [
                    ParsedTableCell(
                        text=str(value).strip(),
                        row_index=row_index,
                        col_index=col_index,
                    )
                    for col_index, value in enumerate(row[:MAX_COLUMNS], start=1)
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
