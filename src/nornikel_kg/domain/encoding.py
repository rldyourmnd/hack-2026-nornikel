from __future__ import annotations

# Russian source files arrive in mixed encodings — UTF-8 (with/without BOM) and
# Windows-1251 are both common. A fixed UTF-8 decode rejected CP1251 CSVs
# outright, so real RU corpora were unusable. Decode through an ordered cascade
# and report which encoding actually worked (persisted in artifact metadata).

_CASCADE = ("utf-8-sig", "utf-8", "cp1251")


def decode_text_bytes(content: bytes) -> tuple[str, str]:
    """Decode bytes to text, returning (text, detected_encoding).

    Tries UTF-8 (BOM-aware) then CP1251 strictly; falls back to
    charset-normalizer detection, and finally a lossy UTF-8 replace so a
    pathological file degrades rather than crashes ingest.
    """
    for encoding in _CASCADE:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(content).best()
        if best is not None:
            return str(best), (best.encoding or "charset-normalizer")
    except Exception:  # pragma: no cover - detector is a best-effort bonus
        pass
    return content.decode("utf-8", errors="replace"), "utf-8-replace"
