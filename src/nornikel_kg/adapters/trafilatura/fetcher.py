from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from nornikel_kg.ports.parser import FetchedPage, ParserError


def assert_public_url(url: str) -> None:
    """SSRF guard: reject non-http(s) schemes and private/loopback/link-local
    hosts (incl. cloud metadata 169.254.169.254) before any fetch.

    URL import accepts an arbitrary URL from the caller; without this a
    request could read internal services or the metadata endpoint and return
    their bodies. Every resolved address for the host must be global.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ParserError(f"Only http/https URLs are allowed: {url}")
    host = parsed.hostname
    if not host:
        raise ParserError(f"URL has no host: {url}")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or 80, proto=socket.IPPROTO_TCP)
    except OSError as error:
        raise ParserError(f"Could not resolve URL host: {host}") from error
    for _family, _type, _proto, _canon, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ParserError(f"URL resolves to a non-public address ({ip}): {url}")


class TrafilaturaUrlFetcher:
    """URL -> clean main text via trafilatura, with title/date metadata."""

    def fetch(self, url: str) -> FetchedPage:
        import trafilatura

        assert_public_url(url)
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            raise ParserError(f"Could not download URL: {url}")
        return self.extract(url=url, html=downloaded)

    def extract(self, *, url: str, html: str) -> FetchedPage:
        import trafilatura

        text = trafilatura.extract(html, output_format="txt", with_metadata=False)
        if not text or not text.strip():
            raise ParserError(f"URL has no extractable main text: {url}")
        metadata = trafilatura.extract_metadata(html)
        title = getattr(metadata, "title", None) if metadata else None
        date = getattr(metadata, "date", None) if metadata else None
        return FetchedPage(url=url, text=text.strip(), title=title, date=date)
