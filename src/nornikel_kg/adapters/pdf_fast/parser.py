from __future__ import annotations

import logging
import pickle
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from nornikel_kg.ports.parser import (
    NoTextLayerError,
    ParsedBlock,
    ParsedDocument,
    ParserError,
)

logger = logging.getLogger(__name__)

_MAX_BLOCK_CHARS = 800


def _chunk_page_text(text: str, max_chars: int) -> list[str]:
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


_WORKER_SCRIPT = r'''
import json, sys, pickle, struct

def _run():
    content_len = struct.unpack("<I", sys.stdin.buffer.read(4))[0]
    content = sys.stdin.buffer.read(content_len)
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(content)
    pages = []
    for i in range(len(pdf)):
        page = pdf[i]
        tp = page.get_textpage()
        text = tp.get_text_range()
        tp.close()
        page.close()
        pages.append(text)
    pdf.close()
    sys.stdout.buffer.write(pickle.dumps(pages))

if __name__ == "__main__":
    _run()
'''


class PyPdfiumFastParser:
    parser_profile = "pypdfium_fast_v1"

    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        extension = Path(filename).suffix.lower()
        if extension != ".pdf":
            raise ParserError(f"PyPdfiumFastParser handles .pdf only, got {extension}")

        pages_text = self._parse_in_subprocess(content, filename)

        blocks: list[ParsedBlock] = []
        ordinal = 0
        for page_index, text in enumerate(pages_text):
            for chunk in _chunk_page_text(text, _MAX_BLOCK_CHARS):
                ordinal += 1
                blocks.append(
                    ParsedBlock(
                        text=chunk, page=page_index + 1, locator=f"block_{ordinal}"
                    )
                )

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

    @staticmethod
    def _parse_in_subprocess(content: bytes, filename: str) -> list[str]:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as script_file:
            script_file.write(_WORKER_SCRIPT)
            script_path = script_file.name

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                input=struct.pack("<I", len(content)) + content,
                capture_output=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired as error:
            raise ParserError(
                f"pypdfium2 subprocess timed out for {filename}: {error}"
            ) from error
        finally:
            Path(script_path).unlink(missing_ok=True)

        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")[:500]
            if "NoTextLayer" in stderr or "no text" in stderr.lower():
                raise NoTextLayerError(
                    f"PDF {filename} has no extractable text layer (OCR is out of scope)."
                )
            raise ParserError(f"pypdfium2 subprocess failed for {filename}: {stderr}")

        try:
            pages: list[str] = pickle.loads(proc.stdout)
        except Exception as error:
            raise ParserError(
                f"pypdfium2 subprocess returned invalid data for {filename}: {error}"
            ) from error

        return pages
