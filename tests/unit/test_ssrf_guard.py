from __future__ import annotations

import pytest

from nornikel_kg.adapters.trafilatura.fetcher import assert_public_url
from nornikel_kg.ports.parser import ParserError


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/x",
        "http://127.0.0.1:8080/api",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
        "http://192.168.1.1/",
    ],
)
def test_blocks_non_public_urls(url: str) -> None:
    with pytest.raises(ParserError):
        assert_public_url(url)


def test_allows_public_https() -> None:
    # example.com resolves to a public address; should not raise
    assert_public_url("https://example.com/article")
