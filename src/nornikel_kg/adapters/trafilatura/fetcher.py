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


# URL-import fetch limits (SSRF + resource caps).
_MAX_URL_HOPS = 4
_MAX_URL_BYTES = 20_000_000
_URL_TIMEOUT_S = 30.0
_URL_USER_AGENT = "nornikel-kg-search/1.0 (+url-import)"


class TrafilaturaUrlFetcher:
    """URL -> clean main text via trafilatura, with title/date metadata."""

    def fetch(self, url: str) -> FetchedPage:
        """Fetch with a controlled client, then extract.

        `trafilatura.fetch_url` follows redirects internally, so validating only
        the initial host is an SSRF hole: a public URL can 3xx-redirect to
        169.254.169.254 or 127.0.0.1. We disable auto-redirects and revalidate
        every hop against `assert_public_url`, and cap the body size.
        """
        import httpx

        assert_public_url(url)
        current = url
        with httpx.Client(follow_redirects=False, timeout=_URL_TIMEOUT_S) as client:
            for _ in range(_MAX_URL_HOPS):
                with client.stream(
                    "GET", current, headers={"User-Agent": _URL_USER_AGENT}
                ) as response:
                    if response.is_redirect and response.next_request is not None:
                        current = str(response.next_request.url)
                        assert_public_url(current)  # revalidate EVERY redirect hop
                        continue
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > _MAX_URL_BYTES:
                            raise ParserError(
                                f"URL body exceeds {_MAX_URL_BYTES} bytes: {current}"
                            )
                    encoding = response.encoding or "utf-8"
                html = bytes(body).decode(encoding, errors="replace")
                if not html.strip():
                    raise ParserError(f"Could not download URL: {current}")
                return self.extract(url=current, html=html)
        raise ParserError(f"Too many redirects for URL: {url}")

    def extract(self, *, url: str, html: str) -> FetchedPage:
        import trafilatura

        text = trafilatura.extract(html, output_format="txt", with_metadata=False)
        if not text or not text.strip():
            raise ParserError(f"URL has no extractable main text: {url}")
        metadata = trafilatura.extract_metadata(html)
        title = getattr(metadata, "title", None) if metadata else None
        date = getattr(metadata, "date", None) if metadata else None
        return FetchedPage(url=url, text=text.strip(), title=title, date=date)
