from __future__ import annotations

from nornikel_kg.domain.encoding import decode_text_bytes


def test_decode_utf8_and_bom() -> None:
    text, enc = decode_text_bytes("материал никель".encode())
    assert text == "материал никель"
    assert enc in {"utf-8", "utf-8-sig"}  # BOM-aware decoder handles both
    text, _enc = decode_text_bytes("шлак".encode("utf-8-sig"))
    assert text == "шлак"


def test_decode_cp1251_russian() -> None:
    raw = "сульфаты 300 мг/л".encode("cp1251")
    text, enc = decode_text_bytes(raw)
    assert text == "сульфаты 300 мг/л"
    assert enc == "cp1251"
