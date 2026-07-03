from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ParserError(RuntimeError):
    """Raised when a document cannot be parsed at all (quarantine path)."""


class NoTextLayerError(ParserError):
    """Raised for PDFs without an extractable text layer (quarantine, never OCR)."""


@dataclass(frozen=True)
class ParsedBlock:
    text: str
    page: int | None = None
    locator: str = ""


@dataclass(frozen=True)
class ParsedTableCell:
    text: str
    row_index: int
    col_index: int


@dataclass(frozen=True)
class ParsedTableRow:
    cells: list[ParsedTableCell]
    row_index: int

    @property
    def text(self) -> str:
        return " | ".join(cell.text for cell in self.cells if cell.text.strip())


@dataclass(frozen=True)
class ParsedTable:
    rows: list[ParsedTableRow]
    table_index: int
    page: int | None = None


@dataclass(frozen=True)
class ParsedDocument:
    blocks: list[ParsedBlock]
    tables: list[ParsedTable]
    title: str | None = None
    parser_profile: str = "unknown"
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def has_content(self) -> bool:
        return any(block.text.strip() for block in self.blocks) or any(
            row.text.strip() for table in self.tables for row in table.rows
        )


@dataclass(frozen=True)
class FetchedPage:
    url: str
    text: str
    title: str | None = None
    date: str | None = None


class DocumentParserPort(Protocol):
    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        """Parse PDF/DOCX bytes into provenance-carrying blocks and tables."""


class UrlFetcherPort(Protocol):
    def fetch(self, url: str) -> FetchedPage:
        """Fetch a URL and extract its main text content plus metadata."""
