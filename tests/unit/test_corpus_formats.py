from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from nornikel_kg.adapters.duckdb.repositories import DuckDBLedgerRepository
from nornikel_kg.adapters.legacy_doc import LegacyDocParser
from nornikel_kg.ports.parser import ParsedBlock, ParsedDocument, ParserError
from nornikel_kg.services.archive_expansion import expand_archives
from nornikel_kg.services.ingestion_service import IngestionService


def _make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def test_plain_zip_expands_ingestible_members(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    _make_zip(archive, {"paper.pdf": b"%PDF-1.4", "notes.gif": b"GIF89a", "data.txt": b"x"})
    extracted, stats = expand_archives([archive], tmp_path / "work")
    names = {path.name for path in extracted}
    assert names == {"paper.pdf", "data.txt"}  # gif is not ingestible
    assert stats["zip_expanded"] == 1


def test_zip_same_basename_different_folders_do_not_collide(tmp_path: Path) -> None:
    """Two report.pdf in different inner folders must both survive (no overwrite)."""
    archive = tmp_path / "bundle.zip"
    _make_zip(
        archive,
        {
            "CRU-2012/report.pdf": b"%PDF-1.4 twelve",
            "CRU-2013/report.pdf": b"%PDF-1.4 thirteen",
        },
    )
    extracted, stats = expand_archives([archive], tmp_path / "work")
    assert len(extracted) == 2  # both kept, not one overwritten
    bodies = {path.read_bytes() for path in extracted}
    assert bodies == {b"%PDF-1.4 twelve", b"%PDF-1.4 thirteen"}
    assert stats["archive_members"] == 2


def test_multipart_zip_is_reassembled(tmp_path: Path) -> None:
    """CM_05_09.zip.001 + .002 style splits concatenate into one valid zip."""
    whole = tmp_path / "whole.zip"
    _make_zip(whole, {"CM_05_09.pdf": b"%PDF-1.4" + b"A" * 5000})
    data = whole.read_bytes()
    part1 = tmp_path / "CM_05_09.zip.001"
    part2 = tmp_path / "CM_05_09.zip.002"
    part1.write_bytes(data[: len(data) // 2])
    part2.write_bytes(data[len(data) // 2 :])
    whole.unlink()

    extracted, stats = expand_archives([part1, part2], tmp_path / "work")
    assert [path.name for path in extracted] == ["CM_05_09.pdf"]
    assert stats["multipart_zip_expanded"] == 1
    assert extracted[0].read_bytes().startswith(b"%PDF-1.4")


def test_zip_slip_member_is_skipped(tmp_path: Path) -> None:
    archive = tmp_path / "evil.zip"
    _make_zip(archive, {"../escape.pdf": b"%PDF-1.4"})
    extracted, _stats = expand_archives([archive], tmp_path / "work")
    # flattened to basename inside work dir, never outside it
    for path in extracted:
        assert path.resolve().is_relative_to((tmp_path / "work").resolve())


def test_corrupt_rar_is_counted_not_crashed(tmp_path: Path) -> None:
    bad = tmp_path / "broken.rar"
    bad.write_bytes(b"not really a rar")
    extracted, stats = expand_archives([bad], tmp_path / "work")
    assert extracted == []
    assert stats["rar_skipped"] == 1


def test_spreadsheet_parser_produces_table_rows(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    pytest.importorskip("pandas")
    from nornikel_kg.adapters.spreadsheet import SpreadsheetDocumentParser

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Материал", "Извлечение", "Единица"])
    sheet.append(["штейн", "95.2", "%"])
    target = tmp_path / "catalog.xlsx"
    workbook.save(target)

    parsed = SpreadsheetDocumentParser().parse(
        content=target.read_bytes(), filename="catalog.xlsx"
    )
    assert parsed.tables
    row_texts = [row.text for table in parsed.tables for row in table.rows]
    assert any("штейн" in text for text in row_texts)
    # E: the worksheet name is carried on the parsed table...
    assert parsed.tables[0].sheet_name == "Sheet"
    # ...and becomes sheet-qualified provenance on ingest.
    repo = DuckDBLedgerRepository(tmp_path / "sheets.duckdb")
    repo.migrate()
    repo.ingest_parsed_document(
        source_id="src_xlsx",
        raw_sha256="deadbeef",
        title="catalog",
        document_type="spreadsheet",
        parsed=parsed,
        artifact_locator="catalog.xlsx",
    )
    spans = repo.list_evidence_spans("src_xlsx")
    assert spans
    assert str(spans[0].locator.get("stable_locator", "")).startswith("sheet:Sheet:")
    assert spans[0].locator.get("sheet") == "Sheet"


def test_legacy_doc_without_text_raises_parser_error() -> None:
    with pytest.raises(ParserError):
        LegacyDocParser().parse(content=b"\xd0\xcf\x11\xe0 garbage", filename="old.doc")


class _StubParser:
    parser_profile = "stub_v1"

    def __init__(self) -> None:
        self.filenames: list[str] = []

    def parse(self, *, content: bytes, filename: str) -> ParsedDocument:
        self.filenames.append(filename)
        return ParsedDocument(
            blocks=[ParsedBlock(text="Обеднение шлака.", page=1, locator="block_1")],
            tables=[],
            title=filename,
            parser_profile=self.parser_profile,
        )


def test_docm_routes_through_document_parser(tmp_path: Path) -> None:
    repository = DuckDBLedgerRepository(tmp_path / "formats.duckdb")
    repository.migrate()
    stub = _StubParser()
    service = IngestionService(repository, parser=stub, synchronous_enrichment=True)
    response = service.ingest_upload(filename="paper.docm", content=b"PK docm bytes")
    assert stub.filenames == ["paper.docm"]
    assert response.source.status in {"completed", "running"}
    assert response.evidence_count >= 1


def test_cp1251_csv_is_accepted(tmp_path: Path) -> None:
    """A Windows-1251 CSV with the experiment schema ingests, not a hard 400."""
    header = (
        "experiment_id,material,regime,temperature_c,duration_h,atmosphere,"
        "property,method,baseline_value,treated_value,unit,effect\n"
    )
    row = "exp_cp,Никель,отжиг,700,8,воздух,твердость,HV10,200,230,HV,increase\n"
    content = (header + row).encode("cp1251")
    repo = DuckDBLedgerRepository(tmp_path / "cp1251.duckdb")
    repo.migrate()
    packet = repo.ingest_source_bytes(filename="cp1251.csv", content=content)
    assert packet is not None
    spans = repo.list_evidence_spans()
    assert any("Никель" in span.visible_text for span in spans)


def test_cp1251_markdown_decodes_cyrillic(tmp_path: Path) -> None:
    """A Windows-1251 .md ingests with correct Cyrillic via the unified decoder,
    not mojibake (the markdown path previously hard-assumed UTF-8)."""
    content = "Обеднение шлака изучено детально.\n".encode("cp1251")
    repo = DuckDBLedgerRepository(tmp_path / "cp1251md.duckdb")
    repo.migrate()
    repo.ingest_source_bytes(filename="report.md", content=content)
    spans = repo.list_evidence_spans()
    assert any("Обеднение шлака" in span.visible_text for span in spans)


def test_xlsx_caps_are_env_configurable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nornikel_kg.adapters.spreadsheet.parser import (
        _DEFAULT_MAX_ROWS_PER_SHEET,
        _cap,
    )

    assert _cap("INGEST_XLSX_MAX_ROWS", _DEFAULT_MAX_ROWS_PER_SHEET) == _DEFAULT_MAX_ROWS_PER_SHEET
    monkeypatch.setenv("INGEST_XLSX_MAX_ROWS", "99999")
    assert _cap("INGEST_XLSX_MAX_ROWS", _DEFAULT_MAX_ROWS_PER_SHEET) == 99999


def test_expand_archives_recurses_into_nested_archives(tmp_path: Path) -> None:
    # A document inside an archive inside an archive must still be recovered.
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("deep/report.txt", "Обеднение шлака изучено детально.")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as archive:
        archive.write(inner, arcname="nested/inner.zip")

    extracted, stats = expand_archives([outer], tmp_path / "work")

    assert any(path.name == "report.txt" for path in extracted)
    assert stats["nested_archives_expanded"] >= 1


def test_expand_archives_handles_archives_within_archives_within_archives(
    tmp_path: Path,
) -> None:
    # Three levels deep — nothing lost.
    level3 = tmp_path / "level3.zip"
    with zipfile.ZipFile(level3, "w") as archive:
        archive.writestr("final.md", "финальный документ")
    level2 = tmp_path / "level2.zip"
    with zipfile.ZipFile(level2, "w") as archive:
        archive.write(level3, arcname="level3.zip")
    top = tmp_path / "top.zip"
    with zipfile.ZipFile(top, "w") as archive:
        archive.write(level2, arcname="level2.zip")

    extracted, _stats = expand_archives([top], tmp_path / "work")

    assert any(path.name == "final.md" for path in extracted)


def test_multipart_rar_secondary_parts_and_pptx_support() -> None:
    from nornikel_kg.services.archive_expansion import (
        INGESTIBLE_EXTENSIONS,
        _is_secondary_rar_part,
    )

    assert _is_secondary_rar_part("CM_09_12.part2.rar")
    assert not _is_secondary_rar_part("CM_09_12.part1.rar")
    assert not _is_secondary_rar_part("report.rar")
    assert ".pptx" in INGESTIBLE_EXTENSIONS
