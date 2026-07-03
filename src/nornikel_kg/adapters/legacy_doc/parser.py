from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from nornikel_kg.ports.parser import ParsedBlock, ParsedDocument, ParserError

logger = logging.getLogger(__name__)


class LegacyDocParser:
    """Legacy .doc text extraction via antiword/catdoc (no OCR, no layout).

    When neither binary is installed the document quarantines with a clear
    reason instead of crashing the ingest — same contract as scanned PDFs.
    """

    parser_profile = "legacy_doc_v1"

    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        if Path(filename).suffix.lower() != ".doc":
            raise ParserError(f"Unsupported legacy-doc extension: {filename}")
        text = self._extract_text(content)
        if not text.strip():
            raise ParserError(
                f"Legacy .doc {filename}: no text extracted "
                "(antiword/catdoc unavailable or empty document)."
            )
        blocks = [
            ParsedBlock(text=paragraph.strip(), page=None, locator=f"block_{index}")
            for index, paragraph in enumerate(text.split("\n\n"), start=1)
            if paragraph.strip()
        ]
        return ParsedDocument(
            blocks=blocks,
            tables=[],
            title=Path(filename).stem,
            parser_profile=self.parser_profile,
        )

    def _extract_text(self, content: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".doc") as handle:
            handle.write(content)
            handle.flush()
            for command in (["antiword", handle.name], ["catdoc", "-w", handle.name]):
                if shutil.which(command[0]) is None:
                    continue
                result = subprocess.run(
                    command, capture_output=True, timeout=120, check=False
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.decode("utf-8", errors="ignore")
                logger.warning(
                    "%s failed on .doc: %s", command[0], result.stderr.decode()[:150]
                )
        return ""
