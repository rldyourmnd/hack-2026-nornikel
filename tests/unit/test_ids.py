from __future__ import annotations

from nornikel_kg.domain.ids import source_id_from_bytes, span_id


def test_source_id_is_stable() -> None:
    assert source_id_from_bytes(b"same") == source_id_from_bytes(b"same")
    assert source_id_from_bytes(b"same") != source_id_from_bytes(b"different")


def test_span_id_does_not_depend_on_extraction_run() -> None:
    first = span_id("src_1", "table", 2, "table_1:row_2", "245 HV", [0, 0, 10, 10])
    second = span_id("src_1", "table", 2, "table_1:row_2", " 245   HV ", [0, 0, 10, 10])
    assert first == second
